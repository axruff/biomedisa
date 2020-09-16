# Download or clone Biomedisa
Download and install [Git](https://github.com/git-for-windows/git/releases/download/v2.28.0.windows.1/Git-2.28.0-64-bit.exe).
```
mkdir git
cd git
git clone https://github.com/biomedisa/biomedisa
```

# Install Microsoft Visual Studio 2017
Download and install [MS Visual Studio](https://visualstudio.microsoft.com/de/thank-you-downloading-visual-studio/?sku=Community&rel=15&rr=https%3A%2F%2Fwww.wintotal.de%2Fdownload%2Fmicrosoft-visual-studio-community-2017%2F).
```
Select "Desktop development with C++"
Install
Restart Windows
```

# Set Path Variables
Open Windows Search  
Type `View advanced system settings`  
Click `Environment Variables...`  
Add the following value to the **System variable** `Path`
```
C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Tools\MSVC\14.16.27023\bin\Hostx64\x64
```

# Create the following User variables
```
Name:   PYTHONPATH
Value:  the path to your biomedisa folder (e.g. C:/Users/USERNAME/git/biomedisa)

Name:   DJANGO_SETTINGS_MODULE
Value:  biomedisa.settings
```

# Create the following System variables
```
Name:   PYTHONPATH
Value:  the path to your biomedisa folder (e.g. C:/Users/USERNAME/git/biomedisa)

Name:   DJANGO_SETTINGS_MODULE
Value:  biomedisa.settings
```

# Install Python and pip
Download and install [Python](https://www.python.org/downloads/windows/).
```
Choose "Latest Python 3 Release"
Scroll to "Files"
Choose "Windows x86-64 executable installer"
Select "Add Python 3.X to PATH"
Install
Disable path length limit
Close
```

# Install MySQL
Download and install [MySQL](https://dev.mysql.com/downloads/installer/).
```
Download "Windows (x86, 32-bit), MSI Installer"
Start Installer
Choose Setup Type "Full"
Use default setup (always Next or Execute)
Set root password (You will need this again during the Biomedisa configuration)
```

# Create biomedisa_database
Open MySQL Shell (e.g. Windows Search `MySQL Shell`).
```
\sql
\connect root@localhost
CREATE DATABASE biomedisa_database;
\q
```

# Install pip packages
Open Command Prompt (e.g. Windows Search `Command Prompt`).
```
pip3 install --upgrade pip pypiwin32 setuptools wheel numpy scipy h5py colorama numba
pip3 install --upgrade imagecodecs-lite tifffile scikit-image opencv-python Pillow
pip3 install --upgrade nibabel medpy SimpleITK django mysqlclient simpleparse
```

# Adapt Biomedisa config
Make `config.py` as a copy of `config_example.py`
```
copy git\biomedisa\biomedisa_app\config_example.py git\biomedisa\biomedisa_app\config.py
```
In particular, adapt the following lines in `biomedisa/biomedisa_app/config.py`
```
'OS' - Must be 'windows'
'PATH_TO_BIOMEDISA' - This is where your biomedisa folder is located e.g. 'C:/Users/USERNAME/git/biomedisa'
'SECRET_KEY' - randomly choose a new key
'DJANGO_DATABASE' - Change this password according to the password set during MySQL setup
'ALLOWED_HOSTS' - ['YOUR_IP', 'localhost', '0.0.0.0']
'DEBUG' - Must be True
'FIRST_QUEUE_NGPUS' - the total number of GPUs available
```

# Set up database
Go to your biomedisa directory (e.g. cd git/biomedisa)
```
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

# Install NVIDIA Driver
Download and install [NVIDIA](https://www.nvidia.com/Download/Find.aspx?lang=en-us).  
Choose *Windows Driver Type:* Standard  
Choose *Recommended/Beta:* Studio Driver

# Install CUDA Toolkit 11.0
Download and install [CUDA Toolkit 11.0](https://developer.nvidia.com/cuda-downloads).

# Disable TDR in Nsight Monitor
```
Windows Search "Nsight Monitor" (run as administrator)
Click the "NVIDIA Nsight" symbol in the right corner of your menu bar
Click Nsight Monitor options
Disable "WDDM TDR Enabled"
Reboot your system
```

# Install Microsoft MPI
Download and install [Microsoft MPI](https://www.microsoft.com/en-us/download/details.aspx?id=57467).
```
Select "msmpisetup.exe" to download
Install
```

# Install PyCUDA and mpi4py
```
pip3 install --upgrade pycuda mpi4py
```

# Verify that PyCUDA is working properly
```
python git/biomedisa/biomedisa_features/pycuda_test.py
```

# Run Biomedisa
If you want to use the 2D slice viewer, run the Command Prompt with "as administrator".
```
python git/biomedisa/manage.py runserver localhost:8080
```

# Open Biomedisa
Open Biomedisa in your local browser http://localhost:8080/ and log in as the `superuser` you created.