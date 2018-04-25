**Building controller image**

From top level repository:

`sudo docker build -t <image_name> .`

*Controller must be run with sudo, as it requires access to the docker control socket.*

**Running controller in interactive mode (development)**

`sudo docker run --rm --name controller -ti -e "STAGE=DEV" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`

**Running controller in detached mode (production)**

`sudo docker run --rm --name controller -ti -e "STAGE=PROD" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`