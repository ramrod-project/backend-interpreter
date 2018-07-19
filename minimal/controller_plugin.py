"""Plugin Template Module
TODO:
- add helper function for function advertisement
- add helper function for job request
"""

from os import environ
import brain.queries.writes
import brain.queries.reads
import brain.jobs


class ControllerPlugin(object):

    def __init__(self, name, functionality=None):
        self.name = name
        self.port = int(environ.get("PORT", "9999"))
        self.functionality = {}
        brain.queries.writes.create_plugin(self.name)
        if functionality:
            self.functionality = functionality
            brain.queries.writes.advertise_plugin_commands(self.name, functionality)
        super().__init__()

    def start(self, logger, signal):
        self._start(logger, signal)

    def _start(self, logger, signal):
        """
        subclass should overwrite this
        :param logger:
        :param signal:
        :return:
        """
        pass

    def request_job(self):
        """Request next job

        This first checks the receive queue to see if there is
        a job waiting, then if the queue is empty, it sends a
        request to the database handler to reply with the next
        new job whose start time is in the past. If a job is
        found that job's status is updated to Pending

        Returns:
            {dict} -- a dictionary describing the job containing
            {
                "id": {string} -- GUID, not needed for plugin,
                "JobTarget": {dict} -- target from Targets table,
                "Status": {string} -- the status of the job,
                "StartTime": {int} -- unix epoch start time,
                "JobCommand": {dict} -- command to run
            }
        """
        job = brain.queries.reads.get_next_job(self.name)
        if job:
            new_status = brain.jobs.transition_success(job['Status'])
            brain.queries.writes.update_job_status(job['id'], new_status)
        return job

    def respond_output(self, job, output):
        """Provide job response output

        This method is a helper method for the plugin
        which is inheriting this base class. The plugin
        must pass this function the job object it
        received from the request_job helper function
        and the corresponding output from the
        command.

        This method also performs some basic type
        checking on the output.

        Arguments:
            job {dict} -- the dictionary object for
            the job received from the database/frontend.
            output {str} -- The data to send to the database
        """
        if not isinstance(output, (bytes, str, int, float)):
            raise TypeError
        brain.queries.writes.write_output(job['id'], output)
        new_status = brain.jobs.transition_success(job['Status'])
        brain.queries.writes.update_job_status(job['id'], new_status)

    def _stop(self, **kwargs):
        """Stop the plugin

        This method should be used and called when the exit signal
        is sent to the program subprocesses. Pass any keyword args
        needed and execute any cleanup required.
        """
        exit(0)
