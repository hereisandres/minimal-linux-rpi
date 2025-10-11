Use vagrant.

Add the following Vagrant file:
```
# Buildroot version to use
RELEASE='2025.08'

### Change here for more memory/cores ###
VM_MEMORY=4096
VM_CORES=2

Vagrant.configure('2') do |config|
	# Disable vbguest plugin due to Ruby 3.4 compatibility issue
	if Vagrant.has_plugin?("vagrant-vbguest")
		config.vbguest.auto_update = false
	end
	
	config.vm.box = 'bento/debian-12'

	config.vm.provider :virtualbox do |v, override|
		v.memory = VM_MEMORY
		v.cpus = VM_CORES
		# Optimize for build performance
		v.customize ["modifyvm", :id, "--ioapic", "on"]
		v.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
	end

	config.vm.provision 'shell' do |s|
		s.inline = 'echo Setting up machine name'

		config.vm.provider :vmware_fusion do |v, override|
			v.vmx['displayname'] = "Buildroot #{RELEASE}"
		end

		config.vm.provider :virtualbox do |v, override|
			v.name = "Buildroot #{RELEASE}"
		end
	end

	# Efficient syncing with exclusions per manual recommendations
	# config.vm.synced_folder ".", "/vagrant", type: "rsync",
	# 	rsync__args: ["--delete", "--archive", "--compress"],
	# 	rsync__exclude: [".git/", "output/", "dl/"]
	
	# Development packages
	config.vm.synced_folder "./vm_packages", "/home/vagrant/work/br-ext/package"

	# Bidirectional sync for build artifacts
	config.vm.synced_folder "./vm_output_images", "/home/vagrant/buildroot-#{RELEASE}/output/images", type: "virtualbox", create: true

	config.vm.provision 'shell', privileged: true, inline: <<-SHELL
		set -euo pipefail
		apt-get -q update
		apt-get -q -y install build-essential libncurses5-dev python3 python3-distutils \
			git ccache rsync file bc bison flex unzip  \
			wget qemu-system-arm libssl-dev device-tree-compiler minicom screen \
			liblzma-dev
		apt-get -q -y autoremove
		apt-get -q -y clean
		mkdir -p /home/vagrant/work /home/vagrant/buildroot_dl /home/vagrant/.ccache
    	chown -R vagrant:vagrant /home/vagrant
		update-locale LC_ALL=C
	SHELL

	config.vm.provision 'shell', privileged: false, inline: <<-SHELL
		echo 'Downloading and extracting buildroot #{RELEASE}'
		wget -q -c http://buildroot.org/downloads/buildroot-#{RELEASE}.tar.gz
		tar axf buildroot-#{RELEASE}.tar.gz
		echo 'Fetching br-ext'
		git clone git@github.com:hereisandres/minimal-linux-rpi.git work/br-ext
	SHELL

end
```
