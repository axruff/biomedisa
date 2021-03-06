##########################################################################
##                                                                      ##
##  Copyright (c) 2020 Philipp Lösel. All rights reserved.              ##
##                                                                      ##
##  This file is part of the open source project biomedisa.             ##
##                                                                      ##
##  Licensed under the European Union Public Licence (EUPL)             ##
##  v1.2, or - as soon as they will be approved by the                  ##
##  European Commission - subsequent versions of the EUPL;              ##
##                                                                      ##
##  You may redistribute it and/or modify it under the terms            ##
##  of the EUPL v1.2. You may not use this work except in               ##
##  compliance with this Licence.                                       ##
##                                                                      ##
##  You can obtain a copy of the Licence at:                            ##
##                                                                      ##
##  https://joinup.ec.europa.eu/page/eupl-text-11-12                    ##
##                                                                      ##
##  Unless required by applicable law or agreed to in                   ##
##  writing, software distributed under the Licence is                  ##
##  distributed on an "AS IS" basis, WITHOUT WARRANTIES                 ##
##  OR CONDITIONS OF ANY KIND, either express or implied.               ##
##                                                                      ##
##  See the Licence for the specific language governing                 ##
##  permissions and limitations under the Licence.                      ##
##                                                                      ##
##########################################################################

import sys, os
import django
django.setup()
import biomedisa_app.views
from django.contrib.auth.models import User

from biomedisa_app.models import Upload
from biomedisa_features.active_contour import active_contour
from biomedisa_features.remove_outlier import remove_outlier
from biomedisa_features.create_slices import create_slices
from biomedisa_features.biomedisa_helper import id_generator
from biomedisa_app.config import config
from biomedisa_features.keras_helper import *
from multiprocessing import Process
import subprocess

from tensorflow.python.framework.errors_impl import ResourceExhaustedError
import numpy as np
import h5py
import time

if config['OS'] == 'linux':
    from redis import Redis
    from rq import Queue

def conv_network(train, predict, refine, img_list, label_list, \
            path_to_model, compress, epochs, batch_size, batch_size_refine, \
            stride_size, stride_size_refining, channels, normalize, path_to_img, \
            x_scale, y_scale, z_scale, balance, image):

    import pycuda.driver as cuda
    cuda.init()
    gpus = cuda.Device.count()
    success = False
    path_to_final = None
    batch_size -= batch_size % gpus                 # batch size must be divisible by number of GPUs
    batch_size_refine -= batch_size_refine % gpus   # batch size must be divisible by number of GPUs
    z_patch, y_patch, x_patch = 64, 64, 64          # dimensions of patches for regular training
    patch_size = 64                                 # x,y,z-patch size for the refinement network
    validation_split = 0.0                          # validation after each epoch

    # adapt scaling and stridesize to patchsize
    stride_size = max(1, min(stride_size, 64))
    stride_size_refining = max(1, min(stride_size, 64))
    x_scale = x_scale - (x_scale - 64) % stride_size
    y_scale = y_scale - (y_scale - 64) % stride_size
    z_scale = z_scale - (z_scale - 64) % stride_size

    if train:

        try:
            # load training data
            img, labelData, position, allLabels, mu, sig, header, extension = load_training_data(normalize, \
                            img_list, label_list, channels, x_scale, y_scale, z_scale)

            # config training data
            x_train, y_train = config_training_data(img, labelData, position, z_patch, y_patch, x_patch, \
                            channels, stride_size, balance)

            # train network
            train_semantic_segmentaion(path_to_model, z_patch, y_patch, x_patch, allLabels, \
                            epochs, batch_size, gpus, x_train, y_train, channels, validation_split)

        except InputError:
            return success, InputError.message, None
        except MemoryError:
            print('MemoryError')
            return success, 'MemoryError', None
        except ResourceExhaustedError:
            print('GPU out of memory')
            return success, 'GPU out of memory', None
        except Exception as e:
            print('Error:', e)
            return success, e, None

        # save meta data
        hf = h5py.File(path_to_model, 'r+')
        group = hf.create_group('meta')
        group.create_dataset('configuration', data=np.array([channels, x_scale, y_scale, z_scale, normalize, mu, sig]))
        group.create_dataset('labels', data=allLabels)
        if extension == '.am':
            group.create_dataset('extension', data=extension)
            group.create_dataset('header', data=header)
        hf.close()

    if refine and not predict:

        try:
            # get meta data
            hf = h5py.File(path_to_model, 'r')
            meta = hf.get('meta')
            configuration = meta.get('configuration')
            channels, x_scale, y_scale, z_scale, normalize, mu, sig = np.array(configuration)[:]
            channels, x_scale, y_scale, z_scale, normalize, mu, sig = int(channels), int(x_scale), \
                                    int(y_scale), int(z_scale), int(normalize), float(mu), float(sig)
            allLabels = meta.get('labels')
            allLabels = np.array(allLabels)
            hf.close()
        except Exception as e:
            print('Error:', e)
            return success, 'Invalid Biomedisa Network', None

        try:
            # load training data
            img, labelData, final = load_training_data_refine(path_to_model, x_scale, y_scale, z_scale, \
                            patch_size, z_patch, y_patch, x_patch, normalize, img_list, label_list, \
                            channels, stride_size, allLabels, mu, sig, batch_size)

            # path to refine model
            path_to_model = path_to_model[:-3] + '_refine.h5'

            # train refinement network
            train_semantic_segmentaion_refine(img, labelData, final, path_to_model, patch_size, epochs, \
                            batch_size_refine, gpus, allLabels, validation_split, stride_size_refining)

            # save meta data
            hf = h5py.File(path_to_model, 'r+')
            group = hf.create_group('meta')
            group.create_dataset('configuration', data=np.array([channels, normalize, mu, sig]))
            group.create_dataset('labels', data=allLabels)
            hf.close()

        except InputError:
            return success, InputError.message, None
        except MemoryError:
            print('MemoryError')
            return success, 'MemoryError', None
        except ResourceExhaustedError:
            print('GPU out of memory')
            return success, 'GPU out of memory', None
        except Exception as e:
            print('Error:', e)
            return success, e, None

    if predict:

        try:
            # get meta data
            hf = h5py.File(path_to_model, 'r')
            meta = hf.get('meta')
            configuration = meta.get('configuration')
            channels, x_scale, y_scale, z_scale, normalize, mu, sig = np.array(configuration)[:]
            channels, x_scale, y_scale, z_scale, normalize, mu, sig = int(channels), int(x_scale), \
                                    int(y_scale), int(z_scale), int(normalize), float(mu), float(sig)
            allLabels = np.array(meta.get('labels'))
            header = np.array(meta.get('header'))
            extension = str(np.array(meta.get('extension')))
            hf.close()
        except Exception as e:
            print('Error:', e)
            return success, 'Invalid Biomedisa Network', None

        # if header is not Amira falling back to Multi-TIFF
        if extension != '.am':
            extension = '.tif'
            header = None

        # create path_to_final
        filename = os.path.basename(path_to_img)
        filename = os.path.splitext(filename)[0]
        if filename[-4:] == '.nii':
            filename = filename[:-4]
        filename = 'final.' + filename
        dir_path = config['PATH_TO_BIOMEDISA'] + '/private_storage/'
        pic_path = 'images/%s/%s' %(image.user.username, filename)
        limit = 100 - len(extension) - len('.cleaned.filled')
        path_to_final = dir_path + pic_path[:limit] + extension

        # if path_to_final exists create new path_to_final
        if os.path.exists(path_to_final):
            CHARACTERS, CODE_SIZE = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz23456789', 7
            newending = id_generator(CODE_SIZE, CHARACTERS)
            limit = 100 - len(extension) - len('.cleaned.filled') - 8
            path_to_final = dir_path + pic_path[:limit] + '_' + newending + extension

        try:
            # load prediction data
            img, position, z_shape, y_shape, x_shape = load_prediction_data(path_to_img, channels, \
                            x_scale, y_scale, z_scale, path_to_model, normalize, mu, sig)

            # make prediction
            predict_semantic_segmentation(img, position, path_to_model, path_to_final, z_patch, y_patch, x_patch, \
                            z_shape, y_shape, x_shape, compress, header, channels, stride_size, allLabels, batch_size)

            # path to refine model
            path_to_model = path_to_model[:-3] + '_refine.h5'

            if refine and os.path.exists(path_to_model):

                # get meta data
                hf = h5py.File(path_to_model, 'r')
                meta = hf.get('meta')
                configuration = meta.get('configuration')
                channels, normalize, mu, sig = np.array(configuration)[:]
                channels, normalize, mu, sig = int(channels), int(normalize), float(mu), float(sig)
                allLabels = meta.get('labels')
                allLabels = np.array(allLabels)
                hf.close()

                # refine segmentation
                refine_semantic_segmentation(path_to_img, path_to_final, path_to_model, patch_size, \
                                             compress, header, normalize, stride_size_refining, \
                                             allLabels, mu, sig, batch_size_refine)

        except InputError:
            return success, InputError.message, None
        except MemoryError:
            print('MemoryError')
            return success, 'MemoryError', None
        except ResourceExhaustedError:
            print('GPU out of memory')
            return success, 'GPU out of memory', None
        except Exception as e:
            print('Error:', e)
            return success, e, None

    success = True
    return success, None, path_to_final

if __name__ == '__main__':

    # time
    TIC = time.time()

    # get objects
    try:
        image = Upload.objects.get(pk=sys.argv[1])
        label = Upload.objects.get(pk=sys.argv[2])
    except Upload.DoesNotExist:
        image.status = 0
        image.pid = 0
        image.save()
        message = 'Files have been removed.'
        Upload.objects.create(user=image.user, project=image.project, log=1, imageType=None, shortfilename=message)

    # check if aborted
    if image.status > 0:

        # set PID
        image.pid = int(os.getpid())
        image.save()

        # get arguments
        model_id = int(sys.argv[3])
        refine_model_id = int(sys.argv[4])
        predict = int(sys.argv[5])
        raw_list = sys.argv[6].split(':')[:-1]
        label_list = sys.argv[7].split(':')[:-1]

        # path to image
        path_to_img = image.pic.path

        # path to files
        path_to_time = config['PATH_TO_BIOMEDISA'] + '/log/time.txt'
        path_to_logfile = config['PATH_TO_BIOMEDISA'] + '/log/logfile.txt'

        # train / refine / predict
        train, refine = False, False
        if predict:
            if refine_model_id > 0:
                refine = True
                refine_model = Upload.objects.get(pk=refine_model_id)
            model = Upload.objects.get(pk=model_id)
            project = os.path.splitext(model.shortfilename)[0]
        else:
            if model_id > 0:
                refine = True
                model = Upload.objects.get(pk=model_id)
                project = os.path.splitext(model.shortfilename)[0]
            else:
                train = True
                project = os.path.splitext(image.shortfilename)[0]

        # write in logs and send notification
        biomedisa_app.views.send_start_notification(image)
        with open(path_to_logfile, 'a') as logfile:
            print('%s %s %s %s' %(time.ctime(), image.user.username, image.shortfilename, 'Process was started.'), file=logfile)
            print('PROJECT:%s PREDICT:%s IMG:%s LABEL:%s RAW_LIST:%s LABEL_LIST:%s' %(project, predict, image.shortfilename, label.shortfilename, raw_list, label_list), file=logfile)

        # create path_to_model
        if train:
            extension = '.h5'
            dir_path = config['PATH_TO_BIOMEDISA'] + '/private_storage/'
            model_path = 'images/%s/%s' %(image.user.username, project)
            limit = 100 - len(extension) - len('_refine')
            path_to_model = dir_path + model_path[:limit] + extension

            # if path_to_model exists create new path_to_model
            if os.path.exists(path_to_model):
                CHARACTERS, CODE_SIZE = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz23456789', 7
                newending = id_generator(CODE_SIZE, CHARACTERS)
                limit = 100 - len(extension) - len('_refine') - 8
                path_to_model = dir_path + model_path[:limit] + '_' + newending + extension
        else:
            path_to_model = model.pic.path

        # parameters
        compress = 6 if label.compression else 0            # wheter final result should be compressed or not
        epochs =  int(label.epochs)                         # epochs the network is trained
        channels = 2 if label.position else 1               # use voxel coordinates
        normalize = 1 if label.normalize else 0             # normalize images before training
        balance = 1 if label.balance else 0                 # the number of training patches must be equal for foreground and background
        x_scale = int(label.x_scale)                        # images are scaled at x-axis to this size before training
        y_scale = int(label.y_scale)                        # images are scaled at y-axis to this size before training
        z_scale = int(label.z_scale)                        # images are scaled at z-axis to this size before training

        # the stride which is made for generating patches
        if model_id > 0:
            stride_size = int(model.stride_size)
            batch_size = int(model.batch_size)
        else:
            stride_size = int(label.stride_size)
            batch_size = int(label.batch_size)
        if refine_model_id > 0:
            stride_size_refining = int(refine_model.stride_size)
            batch_size_refine = int(refine_model.batch_size)
        else:
            stride_size_refining = int(label.stride_size)
            batch_size_refine = int(label.batch_size)

        # train network or predict segmentation
        success, error_message, path_to_final = conv_network(
                                    train, predict, refine, raw_list, label_list, path_to_model, compress, \
                                    epochs, batch_size, batch_size_refine, stride_size, stride_size_refining, channels, \
                                    normalize, path_to_img, x_scale, y_scale, z_scale, balance, image
                                    )

        # reset objects
        image.status = 0
        image.pid = 0
        image.save()

        if success:

            if train:
                # create model object
                short_name = os.path.basename(path_to_model)
                filename = 'images/' + image.user.username + '/' + short_name
                tmp = Upload.objects.create(pic=filename, user=image.user, project=image.project, imageType=4, shortfilename=short_name)
                tmp.friend = tmp.id
                tmp.save()

            if refine and not predict:
                # create model object
                path_to_model = path_to_model[:-3] + '_refine.h5'
                short_name = os.path.basename(path_to_model)
                filename = 'images/' + image.user.username + '/' + short_name
                tmp = Upload.objects.create(pic=filename, user=image.user, project=image.project, imageType=4, shortfilename=short_name)
                tmp.friend = tmp.id
                tmp.save()

            if predict:
                # create final object
                shortfilename = os.path.basename(path_to_final)
                filename = 'images/' + image.user.username + '/' + shortfilename
                tmp = Upload.objects.create(pic=filename, user=image.user, project=image.project, final=1, active=1, imageType=3, shortfilename=shortfilename)
                tmp.friend = tmp.id
                tmp.save()

                # create slices, cleanup and acwe
                q = Queue('slices', connection=Redis())
                job = q.enqueue_call(create_slices, args=(path_to_img, path_to_final,), timeout=-1)
                q = Queue('acwe', connection=Redis())
                job = q.enqueue_call(active_contour, args=(path_to_img, path_to_final, tmp.id, model.id, image.id,), timeout=-1)
                q = Queue('cleanup', connection=Redis())
                job = q.enqueue_call(remove_outlier, args=(path_to_img, path_to_final, tmp.id, model.id,), timeout=-1)

            # write in logs and send notification
            if predict:
                message = 'Successfully segmented ' + project
            else:
                message = 'Successfully trained ' + project
            t = int(time.time() - TIC)
            if t < 60:
                time_str = str(t) + " sec"
            elif 60 <= t < 3600:
                time_str = str(t // 60) + " min " + str(t % 60) + " sec"
            elif 3600 < t:
                time_str = str(t // 3600) + " h " + str((t % 3600) // 60) + " min " + str(t % 60) + " sec"
            with open(path_to_time, 'a') as timefile:
                print('%s %s %s %s on %s' %(time.ctime(), image.user.username, message, time_str, config['SERVER_ALIAS']), file=timefile)
            print('Total calculation time:', time_str)
            biomedisa_app.views.send_notification(image.user.username, image.shortfilename, time_str, config['SERVER_ALIAS'], train)

        else:
            Upload.objects.create(user=image.user, project=image.project, log=1, imageType=None, shortfilename=error_message)
            with open(path_to_logfile, 'a') as logfile:
                print('%s %s %s %s' %(time.ctime(), image.user.username, image.shortfilename, error_message), file=logfile)
            biomedisa_app.views.send_error_message(image.user.username, image.shortfilename, error_message)
