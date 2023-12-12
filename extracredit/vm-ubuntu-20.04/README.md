# Creating the VM

Throughout this assignment, you will use `vagrant` to set-up your VM. 

## Setting up Vagrant

Follow this guide on how to setup the virtual machine, and if you have any questions or issues with this, feel free to ask on Piazza.

### Step 1: Install Vagrant

Vagrant is a tool for automatically configuring a VM using instructions given in a single "Vagrantfile."

**macOS & Windows:** You need to install Vagrant using the correct download link for your computer [here](https://www.vagrantup.com/downloads.html).

**Windows only**: You will be asked to restart your computer at the end of the installation. Click Yes to do so right away, or restart manually later,
but don't forget to do so or Vagrant will not work!

**Linux:** First, make sure your package installer is up to date by running the command `sudo apt-get update`. To install Vagrant, you must have the "Universe" repository on your computer; run `sudo apt-add-repository universe` to add it. Finally, run `sudo apt-get install vagrant` to install vagrant.

### Step 2: Install VirtualBox

VirtualBox is a VM provider (hypervisor). You can skip this if you have already installed VirtualBox.

**macOS & Windows:** You need to install VirtualBox using the correct download link for your computer [here](https://www.virtualbox.org/wiki/Downloads). The links are under the heading "VirtualBox 6.x.x platform packages."

**Windows only:** Use all the default installation settings, but you can uncheck the "Start Oracle VirtualBox 6.x.x after installation" checkbox.

**Linux:** Run the command `sudo apt-get install virtualbox`.

**Note 1:** This will also install the VirtualBox application on your computer, but you should never need to run it, though it may be helpful (see Step 6).

**Note 2:** Some Linux distributions might not provide virtualbox in their package repositories. If the `apt-get install` command is not working for you, you can instead download the latest version of Virtualbox from their website and use `sudo dpkg -i <virtualbox-package.deb> && sudo apt-get install -f` on Debian-based distributions or `sudo rpm localinstall <virtualbox-package.rpm>` on Redhat-based distributions.

### Step 3: Install Git (and SSH-capable terminal on Windows)

Git is a distributed version control system.

**macOS & Windows:** You need to install Git using the correct download link for your computer [here](https://git-scm.com/downloads).

**macOS only:** Once you have opened the .dmg installation file, you will see a Finder window including a .pkg file, which is the installer. Opening this normally may give you a prompt saying it can't be opened because it is from an unidentified developer. To override this protection, instead right-click on thet .pkg file and select "Open". This will show a prompt asking you if you are sure you want to open it. Select "Yes". This will take you to the (straightforward) installation.

**Windows only:** You will be given many options to choose from during the installation; using all the defaults will be sufficient for this course (you can uncheck "View release notes" at the end). The installation includes an SSH-capable Bash terminal usually located at `C:\Program Files\Git\bin\bash.exe`. Another option for a SSH-capable terminal is Windows Powershell.

**Linux:** `sudo apt-get install git`.


### Starting the VM

Start creating a brand new VM by running `vagrant up` in this
directory (install Vagrant on your system if needed). This command
creates a _release_ VM that includes P4 software installed from
pre-compiled packages and allows to update those packages with `apt
upgrade`.



Below are steps that were performed _after_ the command above
was run on the host OS, before creating the VM images. 

+ Log in as user p4 (password p4)
+ Click "Upgrade" in the pop-up window asking if you want to upgrade
  the system, if asked.  This will download the latest Linux kernel
  version released for Ubuntu 20.04, and other updated packages.
+ Reboot the system.
+ `sudo apt clean`

+ Log in as user p4 (password p4)
+ Start menu -> Preferences -> LXQt settings -> Monitor settings
  + Change resolution from initial 800x600 to 1024x768.  Apply the changes.
  + Close monitor settings window
    
+ Start menu -> Preferences -> LXQt settings -> Desktop
  + In "Wallpaper mode" popup menu, choose "Center on the screen".
  + Click Apply button
  + Close "Desktop preferences" window
+ Several of the icons on the desktop have an exclamation mark on
  them.  If you try double-clicking those icons, it pops up a window
  saying "This file 'Wireshark' seems to be a desktop entry.  What do
  you want to do with it?" with buttons for "Open", "Execute", and
  "Cancel".  Clicking "Open" causes the file to be opened using the
  Atom editor.  Clicking "Execute" executes the associated command.
  If you do a mouse middle click on one of these desktop icons, a
  popup menu appears where the second-to-bottom choice is "Trust this
  executable".  Selecting that causes the exclamation mark to go away,
  and future double-clicks of the icon execute the program without
  first popping up a window to choose between Open/Execute/Cancel.  I
  did that for each of these desktop icons:
  + Terminal
  + Wireshark
+ Log off

+ Log in as user vagrant (password vagrant)
+ Change monitor settings and wallpaper mode as described above for
  user p4.
+ Open a terminal.
  + Run the command `./clean.sh`, which removes about 6 to 7 GBytes of
    files created while building the projects.
+ Log off

**Note **: The following commands will allow you to stop the VM at any point (such as when you are done working on an assignment for the day):

* `vagrant suspend` will save the state of the VM and stop it. Always suspend when you are done with the machine.
* `vagrant halt` will gracefully shutdown the VM operating system and power down the VM. Run this to completely stop the machine.
* `vagrant destroy` will remove all traces of the VM from your system. If you have files exclusively saved to your VM, save those to your actual machine before executing this command. 

Additionally, the command `vagrant status` will allow you to check the status of your machine in case you are unsure (e.g. running, powered off, saved...).
You must be in some subdirectory of the directory containing the Vagrantfile to use any of the commands above, otherwise Vagrant will not know which VM you are referring to.


### Common Errors

Here are some fixes to known errors and problems with Vagrant.

#### Error 1: Aftering powering down Vagrant for the first time, `vagrant up` gets stuck on trying to connect to the machine.

This repeated attempt to connect may take anywhere from 1 to 10 minutes. There are a couple of ways to immeditely rectify this, but the easiet method that always works is to use `vagrant destroy` to tear down the virtual machine. Your files will remain on your computer so long as you are saving them to your computer and not exclusively to the vagrant machine. Afterwards, provision the machine the same way in step 6, using `vagrant up`. Make sure to only use `vagrant suspend` as this seems to keep the machine from stalling on starting it up between sessions. 

### Extra Note for Windows users

Line endings are symbolized differently in DOS (Windows) and Unix (Linux/MacOS). In the former, they are represented by a carriage return and line feed (CRLF, or "\r\n"), and in the latter, just a line feed (LF, or "\n"). Given that you ran `git pull` from Windows, git detects your operating system and adds carriage returns to files when downloading. This can lead to parsing problems within the VM, which runs Ubuntu (Unix). Fortunately, this only seems to affect the shell scripts (\*.sh files) we wrote for testing. The `Vagrantfile` is set to automically convert all files back to Unix format, so **you shouldn't have to worry about this**. **However**, if you want to write/edit shell scripts to help yourself with testing, or if you encounter this problem with some other type of file, use the preinstalled program `dos2unix`. Run `dos2unix [file]` to convert it to Unix format (before editing/running in VM), and run `unix2dos [file]` to convert it to DOS format (before editing on Windows). A good hint that you need to do this when running from the VM is some error message involving `^M` (carriage return). A good hint you need to do this when editing on Windows is the lack of new lines. Remember, doing this should only be necessary if you want to edit shell scripts.
