Lab
Cloud Storage: Qwik Start - CLI/SDK
1 Credit
15 minutes
Introductory
Updated 2 days ago
ID: GSP074
GSP074
arrow_drop_down
spark
This lab may incorporate AI tools to support your learning.

GSP074
Google Cloud self-paced labs
Overview
Cloud Storage allows world-wide storage and retrieval of any amount of data at any time. You can use Cloud Storage for a range of scenarios including serving website content, storing data for archival and disaster recovery, or distributing large data objects to users via direct download.

In this hands-on lab you will learn how to create a storage bucket, upload objects to it, create folders and subfolders in it, and make objects publicly accessible using the Google Cloud command line.

Throughout this lab you'll be able to verify your work in the console by going to Navigation menu > Cloud Storage. You'll just need to refresh your browser after each command is run to see the new items you've created.

What you'll do
In this hands-on lab you will learn how to use Google Cloud command line to:

Create a storage bucket
Upload objects to the bucket
Create folders and subfolders in the bucket
Make objects in a storage bucket publicly accessible
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

"Username"
Copied!
You can also find the Username in the Lab setup and access panel.

Click Next.

Copy the Password below and paste it into the Welcome dialog.

"Password"
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
When you are connected, you are already authenticated, and the project is set to your Project_ID, PROJECT_ID. The output contains a line that declares the Project_ID for this session:

Your Cloud Platform project in this session is set to "PROJECT_ID"
gcloud is the command-line tool for Google Cloud. It comes pre-installed on Cloud Shell and supports tab-completion.

(Optional) You can list the active account name with this command:
gcloud auth list
Copied!
Click Authorize.
Output:

ACTIVE: *
ACCOUNT: "ACCOUNT"

To set the active account, run:
    $ gcloud config set account `ACCOUNT`
(Optional) You can list the project ID with this command:
gcloud config list project
Copied!
Output:

[core]
project = "PROJECT_ID"
Note: For full documentation of gcloud, in Google Cloud, refer to the gcloud CLI overview guide.
Set the region
Set the project region for this lab:

gcloud config set compute/region "REGION"
Copied!
Task 1. Create a bucket
In this lab you use gcloud storage commands.

When you create a bucket you must follow the universal bucket naming rules, below.

Bucket naming rules

Do not include sensitive information in the bucket name, because the bucket namespace is global and publicly visible.
Bucket names must contain only lowercase letters, numbers, dashes (-), underscores (_), and dots (.). Names containing dots require verification.
Bucket names must start and end with a number or letter.
Bucket names must contain 3 to 63 characters. Names containing dots can contain up to 222 characters, but each dot-separated component can be no longer than 63 characters.
Bucket names cannot be represented as an IP address in dotted-decimal notation (for example, 192.168.5.4).
Bucket names cannot begin with the "goog" prefix.
Bucket names cannot contain "google" or close misspellings of "google".
Also, for DNS compliance and future compatibility, you should not use underscores (_) or have a period adjacent to another period or dash. For example, ".." or "-." or ".-" are not valid in DNS names.
Use the make bucket (buckets create) command to make a bucket, replacing <YOUR_BUCKET_NAME> with a unique name that follows the bucket naming rules:

gcloud storage buckets create gs://<YOUR-BUCKET-NAME>
Copied!
This command is creating a bucket with default settings. To see what those default settings are, use the Cloud console Navigation menu > Cloud Storage, then click on your bucket name, and click on the Configuration tab.

That's it — you've just created a Cloud Storage bucket!

Note: If the bucket name is already taken, either by you or someone else, the command returns:

Creating gs://YOUR-BUCKET-NAME/...
ServiceException: 409 Bucket YOUR-BUCKET-NAME already exists.

Try again with a different bucket name.
Test completed task
Click Check my progress to verify your performed task. If you've successfully created a Cloud Storage bucket, you'll see an assessment score.

Create a Cloud Storage bucket.
Test your understanding
Below is a multiple choice question to reinforce your understanding of this lab's concepts. Answer it to the best of your ability.


Each bucket has a default storage class, which you can specify when you create your bucket.
True
False

Task 2. Upload an object into your bucket
Use Cloud Shell to upload an object into a bucket.

To download this image (ada.jpg) into your bucket, enter this command into Cloud Shell:
curl https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Ada_Lovelace_portrait.jpg/800px-Ada_Lovelace_portrait.jpg --output ada.jpg
Copied!
Use the gcloud storage cp command to upload the image from the location where you saved it to the bucket you created:
gcloud storage cp ada.jpg gs://YOUR-BUCKET-NAME
Copied!
Note: When typing your bucket name, you can use the tab key to autocomplete it.
You can see the image load into your bucket from the command line.

You've just stored an object in your bucket!

Now remove the downloaded image:
rm ada.jpg
Copied!
Task 3. Download an object from your bucket
Use the gcloud storage cp command to download the image you stored in your bucket to Cloud Shell:
gcloud storage cp -r gs://YOUR-BUCKET-NAME/ada.jpg .
Copied!
If successful, the command returns:

Copying gs://YOUR-BUCKET-NAME/ada.jpg...
/ [1 files][360.1 KiB/2360.1 KiB]
Operation completed over 1 objects/360.1 KiB.
You've just downloaded the image from your bucket.

Task 4. Copy an object to a folder in the bucket
Use the gcloud storage cp command to create a folder called image-folder and copy the image (ada.jpg) into it:
gcloud storage cp gs://YOUR-BUCKET-NAME/ada.jpg gs://YOUR-BUCKET-NAME/image-folder/
Copied!
Note: Compared to local file systems, folders in Cloud Storage have limitations, but many of the same operations are supported.
If successful, the command returns:

Copying gs://YOUR-BUCKET-NAME/ada.jpg [Content-Type=image/png]...
- [1 files] [ 360.1 KiB/ 360.1 KiB]
Operation completed over 1 objects/360.1 KiB
The image file has been copied into a new folder in your bucket.

Test completed task
Click Check my progress to verify your performed task. If you have successfully uploaded an object into a folder in your Cloud Storage bucket, you'll see an assessment score.

Copy an object to a folder in the bucket (ada.jpg).
Task 5. List contents of a bucket or folder
Use the gcloud storage ls command to list the contents of the bucket:
gcloud storage ls gs://YOUR-BUCKET-NAME
Copied!
If successful, the command returns a message similar to:

gs://YOUR-BUCKET-NAME/ada.jpg
gs://YOUR-BUCKET-NAME/image-folder/
That's everything currently in your bucket.

Task 6. List details for an object
Use the gcloud storage ls command, with the -l flag to get some details about the image file you uploaded to your bucket:
gcloud storage ls -l gs://YOUR-BUCKET-NAME/ada.jpg
Copied!
If successful, the command returns a message similar to:

306768  2017-12-26T16:07:570Z  gs://YOUR-BUCKET-NAME/ada.jpg
TOTAL: 1 objects, 30678 bytes (360.1 KiB)
Now you know the image's size and date of creation.

Task 7. Make your object publicly accessible
Use the gcloud storage objects update command to grant all users read permission for the object stored in your bucket:
gcloud storage objects update gs://YOUR-BUCKET-NAME/ada.jpg --add-acl-grant=entity=allUsers,role=READER
Copied!
If successful, the command returns:

Patching gs://YOUR-BUCKET-NAME/ada.jpg...
  Completed 1
Your image is now public, and can be made available to anyone.

Test completed ask
Click Check my progress to verify your performed task. If you have successfully shared an object from your storage bucket, you will see an assessment score.

Make your object publicly accessible
Validate that your image is publicly available.

Go to Navigation menu > Cloud Storage, then click on the name of your bucket.
You should see your image with the Public link box. Click the Copy URL and open the URL in a new browser tab.

Note: Who are you looking at? This is Ada Lovelace, credited with being the first computer programmer. She worked with mathematician and computer pioneer Charles Babbage, who proposed the Analytical Engine.

Her interest in the Analytical Engine lead to translating a paper on the machine by Italian mathematician Luigi Menabrea, adding her own extensive annotations. These notes are considered the first computer program - an algorithm designed to be carried out by the machine. She developed a vision of the capability of computers, going beyond number crunching, and examined how individuals and society relate to technology as a collaborative tool.

Citation: Ada Lovelace. (2015, October 22). Wikimedia Commons, the free media repository. Retrieved 08:01, May 31, 2022 from https://commons.wikimedia.org/w/index.php?title=Ada_Lovelace&oldid=176490980, .
Test your understanding
Below is a multiple choice question to reinforce your understanding of this lab's concepts. Answer it to the best of your ability.


An access control list (ACL) is a mechanism you can use to define who has access to your buckets and objects.
True
False

Task 8. Remove public access
To remove this permission, use the command:
gcloud storage objects update gs://YOUR-BUCKET-NAME/ada.jpg --remove-acl-grant=allUsers
Copied!
If successful, the command returns:

Updating gs://YOUR-BUCKET-NAME/ada.jpg...
You have removed public access to this object.

Verify that you've removed public access by clicking the Refresh button in the console. The checkmark will be removed.
Test your understanding
Below is a multiple choice question to reinforce your understanding of this lab's concepts. Answer it to the best of your ability.


You can stop publicly sharing an object by removing the permission entry that has:
By removing project owner role
By updating storage class
allUsers

Delete objects
Use the gcloud storage rm command to delete an object - the image file in your bucket:
gcloud storage rm gs://YOUR-BUCKET-NAME/ada.jpg
Copied!
If successful, the command returns:

Removing gs://YOUR-BUCKET-NAME/ada.jpg...
Refresh the console. The copy of the image file is no longer stored on Cloud Storage (though the copy you made in the image-folder/ folder still exists).
Congratulations!
You created a storage bucket, organized it by creating folders and subfolders, then uploaded objects to it. You also made objects in your bucket publicly accessible using Cloud Shell.

Next steps / Learn more
This lab is also part of a series of labs called Qwik Starts. These labs are designed to give you a little taste of the many features available with Google Cloud. Search for "Qwik Starts" in the lab catalog to find the next lab you'd like to take!

Google Cloud training and certification
...helps you make the most of Google Cloud technologies. Our classes include technical skills and best practices to help you get up to speed quickly and continue your learning journey. We offer fundamental to advanced level training, with on-demand, live, and virtual options to suit your busy schedule. Certifications help you validate and prove your skill and expertise in Google Cloud technologies.

Manual Last Updated on May 20, 2026

Lab Last Tested February 17, 2026

Copyright 2026 Google LLC. All rights reserved. Google and the Google logo are trademarks of Google LLC. All other company and product names may be trademarks of the respective companies with which they are associated.


gcloud auth list
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud auth list
Credentialed Accounts

ACTIVE: *
ACCOUNT: student-02-96d6f61bfddd@qwiklabs.net

To set the active account, run:
    $ gcloud config set account `ACCOUNT`

student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ 

gcloud config list project
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud config list project
[core]
project = qwiklabs-gcp-03-4093b17784b9

Your active configuration is: [cloudshell-13680]
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ 

Set the region
Set the project region for this lab:

gcloud config set compute/region europe-west1
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud config set compute/region europe-west1
Updated property [compute/region].

Use the make bucket (buckets create) command to make a bucket, replacing <YOUR_BUCKET_NAME> with a unique name that follows the bucket naming rules:

gcloud storage buckets create gs://<YOUR-BUCKET-NAME>
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage buckets create gs://qwiklabs-gcp-03-4093b17784b9
Creating gs://qwiklabs-gcp-03-4093b17784b9/...

To download this image (ada.jpg) into your bucket, enter this command into Cloud Shell:
curl https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Ada_Lovelace_portrait.jpg/800px-Ada_Lovelace_portrait.jpg --output ada.jpg
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ curl https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Ada_Lovelace_portrait.jpg/800px-Ada_Lovelace_portrait.jpg --output ada.jpg
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  2009  100  2009    0     0  40338      0 --:--:-- --:--:-- --:--:-- 41000

Use the gcloud storage cp command to upload the image from the location where you saved it to the bucket you created:
gcloud storage cp ada.jpg gs://YOUR-BUCKET-NAME
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage cp ada.jpg gs://qwiklabs-gcp-03-4093b17784b9
Copying file://ada.jpg to gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg
  Completed files 1/1 | 2.0kiB/2.0kiB  

  Now remove the downloaded image:
rm ada.jpg
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ rm ada.jpg

Task 3. Download an object from your bucket
Use the gcloud storage cp command to download the image you stored in your bucket to Cloud Shell:
gcloud storage cp -r gs://
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage cp -r gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg .
Copying gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg to file://./ada.jpg
  Completed files 1/1 | 2.0kiB/2.0kiB 

  Task 4. Copy an object to a folder in the bucket
Use the gcloud storage cp command to create a folder called image-folder and copy the image (ada.jpg) into it:
gcloud storage cp gs://YOUR-BUCKET-NAME/ada.jpg gs://YOUR-BUCKET-NAME/image-folder/
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage cp gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg gs://qwiklabs-gcp-03-4093b17784b9/image-folder/

Copying gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg to gs://qwiklabs-gcp-03-4093b17784b9/image-folder/ada.jpg
  Completed files 1/1 | 2.0kiB/2.0kiB 

  Task 5. List contents of a bucket or folder
Use the gcloud storage ls command to list the contents of the bucket:
gcloud storage ls gs://YOUR-BUCKET-NAME
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage ls gs://qwiklabs-gcp-03-4093b17784b9
gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg
gs://qwiklabs-gcp-03-4093b17784b9/image-folder/

Task 6. List details for an object
Use the gcloud storage ls command, with the -l flag to get some details about the image file you uploaded to your bucket:
gcloud storage ls -l gs://

student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage ls -l gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg
      2009  2026-08-12T17:35:54Z  gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg
TOTAL: 1 objects, 2009 bytes (1.96kiB)

Task 7. Make your object publicly accessible
Use the gcloud storage objects update command to grant all users read permission for the object stored in your bucket:
gcloud storage objects update gs://YOUR-BUCKET-NAME/ada.jpg --add-acl-grant=entity=allUsers,role=READER
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage objects update gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg --add-acl-grant=entity=allUsers,role=READER
Patching gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg...                                                                                                                                         
  Completed 1 

  Task 8. Remove public access
To remove this permission, use the command:
gcloud storage objects update gs://YOUR-BUCKET-NAME/ada.jpg --remove-acl-grant=allUsers
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage objects update gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg --remove-acl-grant=allUsers
Patching gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg...                                                                                                                                         
  Completed 1  
  ****
  Delete objects
Use the gcloud storage rm command to delete an object - the image file in your bucket:
gcloud storage rm gs://YOUR-BUCKET-NAME/ada.jpg
student_02_96d6f61bfddd@cloudshell:~ (qwiklabs-gcp-03-4093b17784b9)$ gcloud storage rm gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg
Removing objects:
Removing gs://qwiklabs-gcp-03-4093b17784b9/ada.jpg...                                                                                                                                         
  Completed 1/1      

  
