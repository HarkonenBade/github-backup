#!/usr/bin/env bash
set -x
set -e

if [ -f ghbackup.service ]
then
    cd ../..
fi

if [ ! -f ghbackup.py ]
then
    echo "Error: Cannot find ghbackup.py"
    echo "Move to the top dir of the repo and re-run the script"
    exit 1
fi

./ghbackup.py >/dev/null
sudo mv ./ghbackup.yml /etc/
sudo cp ./ghbackup.py /usr/local/bin/
sudo cp -t /etc/systemd/system/ support/systemd/ghbackup.{service,timer}
sudo chmod 664 /etc/systemd/system/ghbackup.{service,timer}
sudo systemctl daemon-reload

if [ -z $EDITOR ]
then
    echo "Please edit /etc/ghbackup.yml with the needed config"
    echo "Then run 'sudo systemctl enable ghbackup.timer' to enable the service"
    exit 0
else
    sudo $EDITOR /etc/ghbackup.yml
    sudo systemctl enable ghbackup.timer
fi