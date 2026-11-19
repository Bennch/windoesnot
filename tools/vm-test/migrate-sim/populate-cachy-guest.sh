#!/usr/bin/env bash
# Run only as root inside the disposable cachy-demo VM, after installing packages.
set -euo pipefail
[[ $(hostname) == cachy-demo && $(systemd-detect-virt) == kvm && $EUID == 0 ]] || { echo 'Expected root in cachy-demo KVM' >&2; exit 1; }
stage=/var/tmp/windoesnot-migrate-fixture
[[ ! -e $stage ]] || { echo 'Fixture staging already exists' >&2; exit 1; }
python3 /home/benni/make-fixture.py "$stage"
id anna >/dev/null 2>&1 || useradd -m -s /bin/bash anna
rsync -aHS "$stage/home/benni/" /home/benni/
rsync -aHS "$stage/home/anna/" /home/anna/
chown -R benni:benni /home/benni
chown -R anna:anna /home/anna
install -d /home/benni/{Documents,Pictures,Projekte,Daten} /opt/example /var/lib/libvirt/images /var/lib/migrate-sim
printf 'Migration test document\n' > /home/benni/Documents/umzug.txt
printf 'Testbild ohne persoenliche Daten\n' > /home/benni/Pictures/testbild.txt
printf 'Test project\n' > /home/benni/Projekte/README.txt
cp "$stage/opt/example/app" /opt/example/app
cp --sparse=always "$stage/var/lib/libvirt/images/test.qcow2" /var/lib/libvirt/images/test.qcow2
chown -R benni:benni /home/benni/Documents /home/benni/Pictures /home/benni/Projekte /home/benni/Daten
truncate -s 1G /var/lib/migrate-sim/daten.img
mkfs.ext4 -F -q /var/lib/migrate-sim/daten.img
printf '%s\n' '/var/lib/migrate-sim/daten.img /home/benni/Daten ext4 loop,nofail 0 0' >> /etc/fstab
mount /home/benni/Daten
printf 'separate mounted test filesystem\n' > /home/benni/Daten/mounted.txt
systemctl enable --now docker.service
systemctl enable --now libvirtd.service
# The real container and volume require a working container registry connection.
docker volume create migration-volume
docker run -d --name migration-demo -v migration-volume:/data alpine:3.21 sh -c 'echo migration-volume-test > /data/data.txt; sleep 2147483647'
docker exec migration-demo sha256sum /data/data.txt
