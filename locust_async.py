from locust import task, TaskSet, HttpLocust, events
from locust.exception import StopLocust
import locust.stats
import os, random
import requests
import time, gevent, sys
import uuid

requests.packages.urllib3.disable_warnings()  #for get_token

client_id = os.environ.get('CLIENT_ID', 'id')  #for get_token.
client_secret = os.environ.get('CLIENT_SECRET', 'secret')  #for get_token.
xsuaa_url = os.environ.get('XSUAA_URL', 'https://host.com')  #for get_token.

token = get_token(client_id, client_secret, xsuaa_url)

api_namespace = os.environ.get('API_NAMESPACE', 'api')
resource = os.environ.get('RESOURCE', 'image')
api_version = os.environ.get('API_VERSION', 'v2')
url_suffix_async = '/' + api_namespace + '/' + api_version + '/' + resource + '/jobs'
host = os.environ.get('HOST', 'https:host.com') + url_suffix_async

num_requests = int(os.getenv('NUM_REQUESTS', '1'))

path = os.path.dirname(os.path.realpath(__file__)) + "/pdffiles/"

locust.stats.CSV_STATS_INTERVAL_SEC = 1

class MyTaskSequence(TaskSet):

	def setup(cls):
		print("Test starting!!")

	def on_start(self):
		self.random_id = str(uuid.uuid4())

	def async_handler(self, poll_interval, timeout=60):
		for i in range(num_requests):
			pdffile = random.choice(os.listdir(path))
			filepath = os.path.join(path, pdffile)
			print("Sending a request" + " " + str(i)+ " \n\n")
			start_time = time.time()
			with self.client.post(url=host, catch_response=True,
				data={"accept":"application/json","Content-Type":"multipart/form-data"},
				files={'files': (pdffile, open(filepath, 'rb'), 'application/pdf')},
				headers={"Authorization": token}) as post_resp:

				try:
					if post_resp.json()['id']:
						request_id = post_resp.json()['id']

				except:
					total_time = int((time.time() - start_time) * 1000)
					events.request_failure.fire(request_type="http", name=host,
										response_time=total_time, exception="An error occured trying to read the file.")
					post_resp.failure("An error occured trying to read the file.")
		
		#poll_for_result
				end_time = time.time() + timeout
				while time.time() < end_time:
					response = self.client.get(url=host + "/" + request_id,
										headers={"Authorization":token})
					
					if response.status_code == 200:
						total_time = int((time.time() - start_time) * 1000)
						events.request_success.fire(request_type="http", name="/user/" + self.random_id,
											response_time=total_time, response_length=0)
						post_resp.success()
						#print(response.status_code)
						break

					elif response.status_code != 202:
						print(response)
						print(response.text)
						total_time = int((time.time() - start_time) * 1000)
						events.request_failure.fire(request_type="http", name="/user/" + self.random_id,
											response_time=total_time, exception="Got " +str(response.status_code)+ " status.")
						post_resp.failure("ERROR")
						print(response.status_code)
						break

					gevent.sleep(poll_interval)

				if time.time() > end_time:
					print(pdffile + "'s Polling timed out!!")
					events.request_failure.fire(request_type="http", name="/user/" + self.random_id,
											response_time=total_time, exception="Polling time-out")
					post_resp.failure("ERROR")
					print(response.status_code)

		if i == num_requests-1:
			self.on_stop()

	def on_stop(self):
		gevent.sleep(2)
		print("My task is done")
		raise StopLocust("My task is done")

	def teardown(cls):
		print("All tasks completed. Exiting!!")
		sys.exit(0)

	@task
	def async(self):
		gevent.spawn(self.async_handler(1.0, 600)) # 1200
	

class WebsiteUser(HttpLocust):

	task_set = MyTaskSequence
	min_wait = int(os.getenv('MIN_WAIT', '0'))
	max_wait = int(os.getenv('MAX_WAIT', '0'))

	host = os.environ.get('HOST', 'https://host.com') + url_suffix_async
