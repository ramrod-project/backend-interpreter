**Building controller image**

From top level repository:

`docker build -t <image_name> .`

*Controller must be run with sudo, as it requires access to the docker control socket.*

**Running controller in interactive mode (development)**

`docker run --rm --name controller -ti -e "STAGE=DEV" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`

**Running controller in detached mode (production)**

`docker run --rm --name controller -ti -e "STAGE=PROD" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`
