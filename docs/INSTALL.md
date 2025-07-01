# Installation
First of all run this in venv like a good girl/boy. I created mine in ~/venv folder you can create yours anywhere you want!!

### Requirements
All the codes are tested in the following environment:
* Linux (tested on Ubuntu 14.04/16.04/18.04/20.04/21.04)
* Python 3.10.18 
* add dead snakes repo so that your torch does not crash!!
* ```shell
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install python3.10 python3.10-venv
    ```
* torch will likely give you cuda uncompatibility error , so to silence that
* PyTorch 1.1 or higher (tested on PyTorch 1.1, 1,3, 1,5~1.10)
* Tested on CUDA 12.9 (Ada Love Lace Arch 4090) and works!
* Spconv version is mentioned in requirements.txt


### Install 

a. Clone this repository.
```shell
git clone https://github.com/open-mmlab/OpenPCDet.git
```

b. Install the dependent libraries as follows:

[comment]: <> (* Install the dependent python libraries: )

[comment]: <> (```)

[comment]: <> (pip install -r requirements.txt )

[comment]: <> (```)

* No need of separatly doing anything I have taken care of spconv and other things...
  
c. In 
```shell
${YOUR_VENV_FOLDER}$/lib/python3.10/site-packages/setuptools/command/develop.py
```
Comment out the below mentioned lines so that you are not stuck in a loop...
```python
import site
import subprocess
import sys

from setuptools import Command
from setuptools.warnings import SetuptoolsDeprecationWarning


class develop(Command):
    """Set up package for development"""

    user_options = [
        ("install-dir=", "d", "install package to DIR"),
        ('no-deps', 'N', "don't install dependencies"),
        ('user', None, f"install in user site-package '{site.USER_SITE}'"),
        ('prefix=', None, "installation prefix"),
        ("index-url=", "i", "base URL of Python Package Index"),
    ]
    boolean_options = [
        'no-deps',
        'user',
    ]

    install_dir = None
    no_deps = False
    user = False
    prefix = None
    index_url = None

    def run(self):
        # cmd = (
        #     [sys.executable, '-m', 'pip', 'install', '-e', '.', '--use-pep517']
        #     + ['--target', self.install_dir] * bool(self.install_dir)
        #     + ['--no-deps'] * self.no_deps
        #     + ['--user'] * self.user
        #     + ['--prefix', self.prefix] * bool(self.prefix)
        #     + ['--index-url', self.index_url] * bool(self.index_url)
        # )
        # subprocess.check_call(cmd)
        pass

    def initialize_options(self):
        DevelopDeprecationWarning.emit()

    def finalize_options(self) -> None:
        pass


class DevelopDeprecationWarning(SetuptoolsDeprecationWarning):
    _SUMMARY = "develop command is deprecated."
    _DETAILS = """
    Please avoid running ``setup.py`` and ``develop``.
    Instead, use standards-based tools like pip or uv.
    """
    _SEE_URL = "https://github.com/pypa/setuptools/issues/917"
    _DUE_DATE = 2025, 10, 31
```
Also on running this on cuda 12.9 for me I encountered cuda version issues which I slapped by commenting out:
```
${YOUR_VENV_FOLDER}$/lib/python3.10/site-packages/torch/utils/cpp_extension.py
```
in that there will be a function which checks pytorch's compatibility with cuda version installed...
since nvidia drivers are backward compatible so we ignore such checks which are time wasters for our precious life
Anyway you will find this function `_check_cuda_version(compiler_name: str, compiler_version: TorchVersion) -> None:`
inside it comment out stuff like:
```python
    if cuda_ver != torch_cuda_version:
        # major/minor attributes are only available in setuptools>=49.4.0
        if getattr(cuda_ver, "major", None) is None:
            # raise ValueError("setuptools>=49.4.0 is required")
        if cuda_ver.major != torch_cuda_version.major:
            # raise RuntimeError(CUDA_MISMATCH_MESSAGE.format(cuda_str_version, torch.version.cuda))
        # warnings.warn(CUDA_MISMATCH_WARN.format(cuda_str_version, torch.version.cuda))
```


d. Install this `pcdet` library and its dependent libraries by running the following command:
```shell
pip install -e .
```

e. Enjoy!! (Remember to undo changes after you are happy , I mostly dont undo things since I want my env not to be upgraded since it creates conflicts... so you can either leave the commented out portions as it is or just uncomment them back. But if you uncomment `_check_cuda_version` then you wont be able to run...but for `develop.py` after installing `pcet` you are good to uncomment it out..)
