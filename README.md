**Building controller image**

From top level repository:

`docker build -t <image_name> .`

*Controller must be run with sudo, as it requires access to the docker control socket.*

**Running controller in interactive mode (development)**

`docker run --rm --name controller -ti -e "STAGE=DEV" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`

**Running controller in detached mode (production)**

`docker run --rm --name controller -ti -e "STAGE=PROD" -e "LOGLEVEL=<DEBUG,INFO,WARNING,ERROR,CRITICAL>" -v /var/run/docker.sock:/var/run/docker.sock <image_name>`

**Testing code changes on your local machine**

Install Travis CI locally (mostly for grins; pytest is probably what you want for your local testing:

`sudo apt install ruby ruby-dev`
`sudo gem install travis`
`sudo apt install pry`

*Install path: /var/lib/gems/
*pry allows access to interactive travis console

`travis console`

Make up a temporary build ID:

`BUILDID="build-$<PCP-branch#>`

View the build log, open the show more button for WORKER INFORMATION and find the INSTANCE line, paste it in here and run:

`INSTANCE="travisci/ci-garnet:packer-1512502276-986baf0"`

Run the headless server:

`docker run --name $BUILDID -dit $INSTANCE /sbin/init`

Run the attached client:

`docker exec -it $BUILDID bash -l`

Now run the job:

`su - travis`


*This gets you to the interactive console for travis
Now Install pytest:

`sudo apt install python-logilab-common`


