Google Skills
Current points:
star
34
Current streak count
0

Contents
Contents
Creating a Persistent Disk
lab iconLab
Creating a Persistent Disk
1 Credit
15 minutes
Introductory
Updated 6 days ago
ID: GSP004
Task 5. Local SSDs
arrow_drop_down
100 / 100
timer
13m




spark
This lab may incorporate AI tools to support your learning.

GSP004
Google Cloud self-paced labs
Overview
Compute Engine lets you create and run virtual machines on Google infrastructure. You can create virtual machines running different operating systems, including multiple flavors of Linux (Debian, Ubuntu, Suse, Red Hat, CoreOS) and Windows Server!

Compute Engine provides persistent disks for use as the primary storage for your virtual machine instances. Like physical hard drives, persistent disks exist independently of the virtual machine. If a VM instance is deleted, its persistent disk retains all data. You can then attach it to a different instance.

Note: There are 2 types of persistent disks:
Standard persistent disk
SSD Persistent disk
Learn more about the differences in Storage Option. Each type of persistent disks will have different capacity limits. Read more in the Persistent Disk documentation.
In this hands-on lab, you'll learn how to create a persistent disk and attach it to a virtual machine.

What you'll learn
Create a new VM instance and attach a persistent disk
Format and mount a persistent disk
Prerequisites
Familiarity with standard Linux text editors such as vim, emacs or nano will be helpful
Setup and requirements
Before you click the Start Lab button
Read these instructions. Labs are timed and you cannot pause them. The timer, which starts when you click Start Lab, shows how long Google Cloud resources are made available to you.

This hands-on lab lets you do the lab activities in a real cloud environment, not in a simulation or demo environment. It does so by giving you new, temporary credentials you use to sign in and access Google Cloud for the duration of the lab.

To complete this lab, you need:

Access to a standard internet browser (Chrome browser recommended).
Note: Use an Incognito (recommended) or private browser window to run this lab. This prevents conflicts between your personal account and the student account, which may cause extra charges incurred to your personal account.
Time to complete the lab—remember, once you start, you cannot pause a lab.
Note: Use only the student account for this lab. If you use a different Google Cloud account, you may incur charges to that account.
How to start your lab and sign in to the Google Cloud console
Click the Start Lab button. If you need to pay for the lab, a dialog opens for you to select your payment method. On the right is the Lab setup and access panel with the following:

The Open Google Cloud console button
The temporary credentials (username and password) that you must use for this lab
Other information, if needed, to step through this lab
Note that the lab timer is located near the top of the page, showing the remaining time.

Click Open Google Cloud console (or right-click and select Open Link in Incognito Window if you are running the Chrome browser).

The lab spins up resources, and then opens another tab that shows the Sign in page.

Tip: Arrange the tabs in separate windows, side-by-side.

Note: If you see the Choose an account dialog, click Use Another Account.
If necessary, copy the Username below and paste it into the Sign in dialog.

student-01-5f941bb8d282@qwiklabs.net
Copied!
You can also find the Username in the Lab setup and access panel.

Click Next.

Copy the Password below and paste it into the Welcome dialog.

ehiK0yIGxI9r
Copied!
You can also find the Password in the Lab setup and access panel.

Click Next.

Important: You must use the credentials the lab provides you. Do not use your Google Cloud account credentials.
Note: Using your own Google Cloud account for this lab may incur extra charges.
Click through the subsequent pages:

Accept the terms and conditions.
Do not add recovery options or two-factor authentication (because this is a temporary account).
Do not sign up for free trials.
After a few moments, the Google Cloud console opens in this tab.

Note: To access Google Cloud products and services, click the Navigation menu or type the service or product name in the Search field. Navigation menu icon and Search field
Activate Cloud Shell
Cloud Shell is a virtual machine that is loaded with development tools. It offers a persistent 5GB home directory and runs on the Google Cloud. Cloud Shell provides command-line access to your Google Cloud resources.

Click Activate Cloud Shell Activate Cloud Shell icon at the top of the Google Cloud console.

Click through the following windows:

Continue through the Cloud Shell information window.
Authorize Cloud Shell to use your credentials to make Google Cloud API calls.
When you are connected, you are already authenticated, and the project is set to your Project_ID, qwiklabs-gcp-03-6a03615deed7. The output contains a line that declares the Project_ID for this session:

Your Cloud Platform project in this session is set to qwiklabs-gcp-03-6a03615deed7
gcloud is the command-line tool for Google Cloud. It comes pre-installed on Cloud Shell and supports tab-completion.

(Optional) You can list the active account name with this command:
gcloud auth list
Copied!
Click Authorize.
Output:

ACTIVE: *
ACCOUNT: student-01-5f941bb8d282@qwiklabs.net

To set the active account, run:
    $ gcloud config set account `ACCOUNT`
(Optional) You can list the project ID with this command:
gcloud config list project
Copied!
Output:

[core]
project = qwiklabs-gcp-03-6a03615deed7
Note: For full documentation of gcloud, in Google Cloud, refer to the gcloud CLI overview guide.
Set the region and zone
Set the project region and zone for this lab:
gcloud config set compute/zone us-east1-d
gcloud config set compute/region us-east1
Copied!
Create a variable for region:
export REGION=us-east1
Copied!
Create a variable for zone:
export ZONE=us-east1-d
Copied!
Learn more from the Regions & Zones documentation.

Note: When you run gcloud on your own machine, the config settings are persisted across sessions. But in Cloud Shell, you need to set this for every new session or reconnection.
Task 1. Create a new instance
First, create a Compute Engine virtual machine instance that has only a boot disk.

Note: You can learn more by creating a virtual machine instance in a different lab, or refer to the Compute Engine documentation.
In Cloud Shell command line, use the gcloud command to create a new virtual machine instance named gcelab:
gcloud compute instances create gcelab \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --image-family=debian-12 \
  --image-project=debian-cloud
Copied!
Example Output:

Created [...].
NAME       ZONE           MACHINE_TYPE  PREEMPTIBLE INTERNAL_IP EXTERNAL_IP    STATUS
gcelab     us-east1-d e2-standard-2             10.240.X.X  X.X.X.X        RUNNING
The newly created virtual machine instance will have a default 10 GB persistent disk as the boot disk.

Click Check my progress to verify the objective.

Create a new instance in the specified zone.
Task 2. Create a new persistent disk
Note: Because you want to attach this disk to the virtual machine instance you created in the previous step, the zone must be the same.
Still in the Cloud Shell command line, use the following command to create a new disk named mydisk:
gcloud compute disks create mydisk --size=200GB \
--zone $ZONE
Copied!
Output:

NAME   ZONE          SIZE_GB TYPE        STATUS
mydisk us-east1-d 200      pd-standard READY
Click Check my progress to verify the objective.

Create a new persistent disk in the specified zone
Task 3. Attaching a disk
Attaching the persistent disk
You can attach a disk to a running virtual machine. Attach the new disk (mydisk) to the virtual machine instance you just created (gcelab).

Use the following command to attach the disk:
gcloud compute instances attach-disk gcelab --disk mydisk --zone $ZONE
Copied!
Output:

Updated [https://www.googleapis.com/compute/v1/projects/qwiklabs-gcp-d12e3215bb368ac5/zones/us-east1-d/instances/gcelab].
That's it!

Finding the persistent disk in the virtual machine
The persistent disk is now available as a block device in the virtual machine instance. Let's take a look.

SSH into the virtual machine:
gcloud compute ssh gcelab --zone $ZONE
Copied!
Output:

WARNING: The public SSH key file for gcloud does not exist.
WARNING: The private SSH key file for gcloud does not exist.
WARNING: You do not have an SSH key for gcloud.
WARNING: SSH keygen will be executed to generate a key.
This tool needs to create the directory
[/home/gcpstaging8246_student/.ssh] before being able to generate SSH
keys.
Do you want to continue (Y/n)?  y
At the prompt, enter Y to continue.
When prompted for an RSA key pair passphrase, press ENTER for no passphrase, and then press ENTER again to confirm no passphrase.
Output:

Generating public/private rsa key pair.
Enter passphrase (empty for no passphrase): 
Enter same passphrase again: 
Your identification has been saved in /home/student_02_83e3b522f6bb/.ssh/google_compute_engine
Your public key has been saved in /home/student_02_83e3b522f6bb/.ssh/google_compute_engine.pub
The key fingerprint is:
SHA256:7bX6GGvW8XzO66HjvtKSFYcoL/X1qACuSYLV9iZkhuQ student_02_83e3b522f6bb@cs-266460278491-default
The key's randomart image is:
+---[RSA 3072]----+
|                 |
|    .            |
|   o o      . .  |
|    E * .o o o o |
|   o = oS.= o +..|
|  . . o +o.o.+. .|
|     o =  +o== . |
|      o   oOoo+.o|
|         o+.*=+=+|
+----[SHA256]-----+
Warning: Permanently added 'compute.4080080550383484568' (ED25519) to the list of known hosts.
Linux gcelab 6.1.0-49-cloud-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.174-1 (2026-05-26) x86_64

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Creating directory '/home/student-02-83e3b522f6bb'.
Now find the disk device by listing the disk devices in /dev/disk/by-id/.:
ls -l /dev/disk/by-id/
Copied!
Output:

lrwxrwxrwx 1 root root  9 Jun 24 11:33 google-persistent-disk-0 -> ../../sda
lrwxrwxrwx 1 root root 10 Jun 24 11:33 google-persistent-disk-0-part1 -> ../../sda1
lrwxrwxrwx 1 root root 11 Jun 24 11:33 google-persistent-disk-0-part14 -> ../../sda14
lrwxrwxrwx 1 root root 11 Jun 24 11:33 google-persistent-disk-0-part15 -> ../../sda15
lrwxrwxrwx 1 root root  9 Jun 24 11:34 google-persistent-disk-1 -> ../../sdb
lrwxrwxrwx 1 root root  9 Jun 24 11:33 scsi-0Google_PersistentDisk_persistent-disk-0 -> ../../sda
lrwxrwxrwx 1 root root 10 Jun 24 11:33 scsi-0Google_PersistentDisk_persistent-disk-0-part1 -> ../../sda1
lrwxrwxrwx 1 root root 11 Jun 24 11:33 scsi-0Google_PersistentDisk_persistent-disk-0-part14 -> ../../sda14
lrwxrwxrwx 1 root root 11 Jun 24 11:33 scsi-0Google_PersistentDisk_persistent-disk-0-part15 -> ../../sda15
lrwxrwxrwx 1 root root  9 Jun 24 11:34 scsi-0Google_PersistentDisk_persistent-disk-1 -> ../../sdb
You found the file, the default name is:

scsi-0Google_PersistentDisk_persistent-disk-1.

Note: If you want a different device name, when you attach the disk, you would specify the device-name parameter. For example, to specify a device name, when you attach the disk you would use the command:
gcloud compute instances attach-disk gcelab --disk mydisk --device-name <YOUR_DEVICE_NAME> --zone $ZONE
Formatting and mounting the persistent disk
Once you find the block device, you can partition the disk, format it, and then mount it using the following Linux utilities:

mkfs: creates a filesystem
mount: attaches to a filesystem
Make a mount point:
sudo mkdir /mnt/mydisk
Copied!
Next, format the disk with a single ext4 filesystem using the mkfs tool. This command deletes all data from the specified disk:
sudo mkfs.ext4 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/scsi-0Google_PersistentDisk_persistent-disk-1
Copied!
Last lines of the output:

Allocating group tables: done
Writing inode tables: done
Creating journal (262144 blocks): done
Writing superblocks and filesystem accounting information: done
Now use the mount tool to mount the disk to the instance with the discard option enabled:
sudo mount -o discard,defaults /dev/disk/by-id/scsi-0Google_PersistentDisk_persistent-disk-1 /mnt/mydisk
Copied!
That's it!

Automatically mount the disk on restart
By default the disk will not be remounted if your virtual machine restarts. To make sure the disk is remounted on restart, you need to add an entry into /etc/fstab.

Open /etc/fstab in nano to edit:
sudo nano /etc/fstab
Copied!
Add the following below the line that starts with "PARTUUID=...":
/dev/disk/by-id/scsi-0Google_PersistentDisk_persistent-disk-1 /mnt/mydisk ext4 defaults 1 1
Copied!
/etc/fstab content should look like this:

# /etc/fstab: static file system information
PARTUUID=12adc097-f36f-46f9-b377-b2a30cdf422f / ext4 rw,discard,errors=remount-ro,x-systemd.growfs 0 1
PARTUUID=3A31-89F9 /boot/efi vfat defaults 0 0
/dev/disk/by-id/scsi-0Google_PersistentDisk_persistent-disk-1 /mnt/mydisk ext4 defaults 1 1
Save and exit nano by pressing CTRL+O, ENTER, CTRL+X, in that order.
Click Check my progress to verify the objective.

Attaching and Mounting the persistent disk.
Task 4. Test your knowledge
Test your knowledge about Google cloud Platform by taking this quiz.


Can you prevent the destruction of an attached persistent disk when the instance is deleted?

No, attached persistent disks are always associated with the lifetime of the instance
check
Yes, deselect the option `Delete boot disk when instance is deleted` when creating an instance
check
Yes, use the `–keep-disks` option with the `gcloud compute instances delete` command

For migrating data from a persistent disk to another region, reorder the following steps in which they should be performed:

Attach disk
Create disk
Create snapshot
Create instance
Unmount file system(s)

Choose the correct order
close
(1, 3, 2, 4, 5)
close
(2, 3, 1, 4, 5)
check
(5, 3, 2, 4, 1)
(4, 1, 2, 3, 5)

Task 5. Local SSDs
Compute Engine can also attach local SSDs. Local SSDs are physically attached to the server hosting the virtual machine instance to which they are mounted. This tight coupling offers superior performance, with very high input/output operations per second (IOPS) and very low latency compared to persistent disks.

Local SSD performance offers:

Less than 1 ms of latency
Up to 680,000 read IOPs and 360,000 write IOPs
These performance gains require certain trade-offs in availability, durability, and flexibility. Because of these trade-offs, local SSD storage is not automatically replicated. You can lose all data if a host error or configuration issue makes the disk unreachable. Users must take extra precautions to backup their data.

This lab does not cover local SSDs.

To maximize the local SSD performance, you'll need to use a special Linux image that supports NVMe. You can learn more about local SSDs in the Local SSD documentation.
Congratulations!
You've learned how to create, find, and attach persistent disks to a virtual machine instance and the key difference between persistent disks and local SSDs. You can use persistent disks to setup and configure your database servers.

Next steps / Learn more
Persistent Disk documentation
gcloud CLI documentation and tutorial video.
Google Cloud training and certification
...helps you make the most of Google Cloud technologies. Our classes include technical skills and best practices to help you get up to speed quickly and continue your learning journey. We offer fundamental to advanced level training, with on-demand, live, and virtual options to suit your busy schedule. Certifications help you validate and prove your skill and expertise in Google Cloud technologies.

Manual Last Updated: June 24, 2026

Lab Last Tested: June 24, 2026

Copyright 2026 Google LLC. All rights reserved. Google and the Google logo are trademarks of Google LLC. All other company and product names may be trademarks of the respective companies with which they are associated.




To run a command as administrator (user "root"), use "sudo <command>".
See "man sudo_root" for details.

Welcome to Cloud Shell! Type "help" to get started.
Your Cloud Platform project in this session is set to qwiklabs-gcp-03-6a03615deed7.
Use `gcloud config set project [PROJECT_ID]` to change to a different project.
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud auth list
Credentialed Accounts

ACTIVE: *
ACCOUNT: student-01-5f941bb8d282@qwiklabs.net

To set the active account, run:
    $ gcloud config set account `ACCOUNT`

student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud config list project
[core]
project = qwiklabs-gcp-03-6a03615deed7

Your active configuration is: [cloudshell-7265]
[environment: untagged] Read more to tag: g.co/cloud/project-env-tag.
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud config set compute/zone us-east1-d
gcloud config set compute/region us-east1
Updated property [compute/zone].
Updated property [compute/region].
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ export REGION=us-east1
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ export ZONE=us-east1-d
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud compute instances create gcelab \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --image-family=debian-12 \
  --image-project=debian-cloud
Created [https://www.googleapis.com/compute/v1/projects/qwiklabs-gcp-03-6a03615deed7/zones/us-east1-d/instances/gcelab].
NAME: gcelab
ZONE: us-east1-d
MACHINE_TYPE: e2-standard-2
PREEMPTIBLE: 
INTERNAL_IP: 10.142.0.2
EXTERNAL_IP: 34.75.218.217
STATUS: RUNNING
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud compute disks create mydisk --size=200GB \
--zone $ZONE
Created [https://www.googleapis.com/compute/v1/projects/qwiklabs-gcp-03-6a03615deed7/zones/us-east1-d/disks/mydisk].
NAME: mydisk
ZONE: us-east1-d
SIZE_GB: 200
TYPE: pd-standard
STATUS: READY

New disks are unformatted. You must format and mount a disk before it
can be used. You can find instructions on how to do this at:

For Linux: https://cloud.google.com/compute/docs/disks/format-mount-disk-linux
For Windows: https://cloud.google.com/compute/docs/disks/format-mount-disk-windows

student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud compute instances attach-disk gcelab --disk mydisk --zone $ZONE
Updated [https://www.googleapis.com/compute/v1/projects/qwiklabs-gcp-03-6a03615deed7/zones/us-east1-d/instances/gcelab].
student_01_5f941bb8d282@cloudshell:~ (qwiklabs-gcp-03-6a03615deed7)$ gcloud compute ssh gcelab --zone $ZONE
WARNING: The private SSH key file for gcloud does not exist.
WARNING: The public SSH key file for gcloud does not exist.
WARNING: You do not have an SSH key for gcloud.
WARNING: SSH keygen will be executed to generate a key.
This tool needs to create the directory [/home/student_01_5f941bb8d282/.ssh] before being 
able to generate SSH keys.

Do you want to continue (Y/n)?  Y

Generating public/private rsa key pair.
Enter passphrase (empty for no passphrase): 
Enter same passphrase again: 
Your identification has been saved in /home/student_01_5f941bb8d282/.ssh/google_compute_engine
Your public key has been saved in /home/student_01_5f941bb8d282/.ssh/google_compute_engine.pub
The key fingerprint is:
SHA256:Qg3/tJei68B/rn40SUXOy4veFXVSq7G+6SfL3JAP4ZM student_01_5f941bb8d282@cs-401150240569-default
The key's randomart image is:
+---[RSA 3072]----+
|      .    ..   .|
|       +   o.  ..|
|      . o ..o...o|
|     .   o.o o+o.|
|      . S.+.=+.  |
|     . . .++o.+. |
|      o .....E.  |
|       o oo.ooO. |
|       o*=o oB+o |
+----[SHA256]-----+
Warning: Permanently added 'compute.9121220748162704766' (ED25519) to the list of known hosts.
Linux gcelab 6.1.0-52-cloud-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.180-1 (2026-08-03) x86_64

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Creating directory '/home/student-01-5f941bb8d282'.
student-01-5f941bb8d282@gcelab:~$ ls -l /dev/disk/by-id/
total 0
  GNU nano 7.2                             /etc/fstab *                                     
/dev/disk/by-id/scsi-0Google_PersistentDisk_persistent-disk-1 /mnt/mydisk ext4 defaults 1 1





PARTUUID=c837c4b5-0a83-4340-8247-27e9d20f95c4 / ext4 rw,discard,errors=remount-ro,x-systemd>
PARTUUID=cd30364b-1707-4901-8ac8-6a69d619b296 /boot/efi vfat defaults 0 0
