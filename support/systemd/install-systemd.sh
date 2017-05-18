#!/usr/bin/env bash
set -x
set -e

if [ -f github-backup.service ]
then
    cd ../..
fi

if [ ! -f github-backup.py ]
then
    echo "Error: Cannot find github-backup.py"
    echo "Move to the top dir of the repo and re-run the script"
    exit 1
fi

./github-backup.py >/dev/null
sudo mv ./github-backup.yml /etc/
sudo cp ./github-backup.py /usr/local/bin/
sudo cp -t /etc/systemd/system/ support/systemd/github-backup.{service,timer}
sudo chmod 664 /etc/systemd/system/github-backup.{service,timer}
sudo systemctl daemon-reload

if [ -z $EDITOR ]
then
    echo "Please edit /etc/github-backup.yml with the needed config"
    echo "Then run 'sudo systemctl enable github-backup.timer' to enable the service"
    exit 0
else
    sudo $EDITOR /etc/github-backup.yml
    sudo systemctl enable github-backup.timer
fi