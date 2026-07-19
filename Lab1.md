Infrastructure as Code with Terraform

What means Terraform  in Google cloud in simple english with example? 

In simple English, Terraform is a tool that lets you create and manage Google Cloud resources by writing code instead of clicking buttons in the Google Cloud Console.

Think of it like this:

Without Terraform: You manually create a VM, network, firewall, and storage bucket by clicking through the Google Cloud website.

With Terraform: You write a small text file that describes what you want, and Terraform creates everything automatically.


Example 1: Creating a Virtual Machine

Instead of going to the Google Cloud Console and creating a VM manually, you write:

resource "google_compute_instance" "my_vm" {
  name         = "my-vm"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    network = "default"
  }
}

Then run:

terraform init
terraform plan
terraform apply

Terraform creates the VM for you.


---

Example 2: Creating a Storage Bucket

Instead of clicking Create Bucket in Google Cloud, you write:

resource "google_storage_bucket" "my_bucket" {
  name     = "my-example-bucket-12345"
  location = "US"
}

Running terraform apply creates the bucket automatically.


---

Real-Life Analogy

Imagine you want to build a house.

Without Terraform: You tell workers every step each time you build a house.

With Terraform: You give them a blueprint. They build the house exactly the same way every time.


Terraform is that blueprint for your cloud infrastructure.


---

Why do companies use Terraform?

✅ Saves time by automating cloud setup.

✅ Reduces mistakes from manual work.

✅ Everyone uses the same configuration.

✅ Easy to recreate environments (development, testing, production).

✅ Changes can be tracked using version control like Git.



---

Common Google Cloud resources you can create with Terraform

Virtual Machines (VMs)

Storage Buckets

Networks and Subnets

Firewalls

Cloud SQL databases

Kubernetes (GKE) clusters

Service Accounts

Load Balancers



---

Simple workflow

1. Write what you want in a Terraform file (.tf).


2. Run terraform plan to see what Terraform will do.


3. Run terraform apply to create or update the resources.


4. If you no longer need them, run terraform destroy to remove them.



In short, Terraform is an Infrastructure as Code (IaC) tool. It lets you define your Google Cloud infrastructure in code, making it easy to create, update, and manage cloud resources consistently and automatically.
