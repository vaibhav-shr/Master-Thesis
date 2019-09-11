import requests, json, time, datetime
import sys, os
import signal, time
import subprocess
import pandas as pd
import argparse
import pickle
import glob, shutil
import analysis
from sklearn.utils import resample
import statistics
import numpy as np
import matplotlib.pyplot as plt

path = os.path.dirname(os.path.realpath(__file__))

def runtest(fname, ftest, mint, maxt, boot):
	#deploy locust files
	os.system('kubectl create -f kubernetes_config/locust-async-master-controller.yaml')
	os.system('kubectl create -f kubernetes_config/locust-async-worker-controller.yaml')
	os.system('kubectl create -f kubernetes_config/locust-async-master-service.yaml')

	#find master pod to download files
	time.sleep(5)
	p = subprocess.check_output('kubectl get pods --namespace=vaibhav | grep locust-master', shell=True)
	p = str(p)
	p = p.split()[0]
	master = p[2:]

	#start monitor when test starts
	#test starts when cpu is above 15%
	print("Waiting for the test to start!")
	while(True):
		T, pods, cpu, mem = monitor()
		if cpu>(0.15*pods):
			break
		time.sleep(30)

	#start monitor and store
	print("Monitoring starts!!")
	columns = ['Time', 'Pods', 'CPU', 'Mem']
	df = pd.DataFrame(index=None, columns=columns)

	while(True):
		T, pods, cpu, mem = monitor()
		if cpu<(0.1*pods):
			print('CPU is: ' + str(cpu) + '! Stopping Monitoring')
			break
		lst_dict = []
		lst_dict.append({'Time':T, 'Pods':pods, 'CPU':cpu, 'Mem':mem})
		df = df.append(lst_dict)
		#print(df)
		time.sleep(30)

	#Test completed
	print('Downloading files.')
	#download metrices and resource profile
	time.sleep(10) #wait till slaves send complete data to master
	name = fname
	# if not bootstrapping, both locust and resource usage data are saved by creating respective folders
	if boot == 'n':
		dirname = str(path)+'/'+str(int(pods))+'_pod/'
		if not os.path.exists(dirname):
			os.makedirs(dirname)
			os.system('kubectl cp vaibhav/'+str(master)+':'+str(name)+'_requests.csv'+' '+str(path)+'/'+str(int(pods))+'_pod/')
		else:
			os.system('kubectl cp vaibhav/'+str(master)+':'+str(name)+'_requests.csv'+' '+str(path)+'/'+str(int(pods))+'_pod/')

		dirnameres = path+'/'+str(int(pods))+'_pod/resource/'
		if not os.path.exists(dirnameres):
			os.makedirs(dirnameres)
			df.to_csv(path+'/'+str(int(pods))+'_pod/resource/'+str(name)+'_resource.csv', encoding='utf-8', index=False)
		else:
			df.to_csv(path+'/'+str(int(pods))+'_pod/resource/'+str(name)+'_resource.csv', encoding='utf-8', index=False)

	# if bootstrapping, we need only locust results to calculate throughput
	elif boot == 'y':
		dirname = str(path)+'/'+str(int(pods))+'_pod/bootstrap/'
		if not os.path.exists(dirname+str(int(pods))+'_pod'):
			os.makedirs(dirname+str(int(pods))+'_pod')
			os.system('kubectl cp vaibhav/'+str(master)+':'+str(name)+'_requests.csv'+' '+str(dirname)+str(int(pods))+'_pod')
		else:    
			os.system('kubectl cp vaibhav/'+str(master)+':'+str(name)+'_requests.csv'+' '+str(dirname)+str(int(pods))+'_pod')

		bootstrap(dirname, int(pods))

	print("Data downloaded. Please delete the replication controllers and the service!")

	if ftest == 'y':
		test_recommender(fname)
		write_file()

def test_recommender(fname, mint, maxt):
	req = int(fname)
	mint = 2*mint
	maxt = 2*maxt
	com_path = path + '/1_pod/'
	df = pd.read_csv(com_path+'resource/'+str(fname)+'_resource.csv')
	total_time_spent = len(df.index)
	if (total_time_spent < mint) or (total_time_spent >= maxt):
		recm_req_1_pod = round((req * 4) / total_time_spent)
		print("repeat first test with 1 pod and "+str(recm_req_1_pod)+" requests!")
		os.remove(''+str(com_path)+'resource/'+str(fname)+'_resource.csv')
		os.remove(''+str(com_path)+'/'+str(fname)+'_requests.csv')
	elif (total_time_spent >= mint) and (total_time_spent < maxt):
		print("First test looks good. The following testing pattern is recommended:")
		print("1 pod -----> "+str(req)+" requests")
		next_req = int((req / 2) + req)
		print("1 pod -----> "+str(next_req)+" requests")
		ten_req = int(req * 10)
		print("10 pods -----> "+str(ten_req)+" requests")
		next_ten_req = int((ten_req / 2) + ten_req)
		print("10 pods -----> "+str(next_ten_req)+" requests")
		print("20 pods -----> "+str(next_ten_req)+" requests")
		next_twen_req = int((next_ten_req / 2) + next_ten_req)
		print("20 pods -----> "+str(next_twen_req)+" requests")

def write_file():
	pod = [1, 10, 20]
	with open("data.txt", "wb") as fp:
		pickle.dump(pod, fp)

# Bootstrapping with number of samples = number of throughputs. Size of each sample (n_samples) = number of throughputs.
def bootstrapping(throughput):
	size = len(throughput)
	boot_mean = []
	for i in range(size):
		boot = resample(throughput, replace=True, n_samples=size)
		avg = statistics.mean(boot)
		boot_mean.append(avg)
	n, bins, patches = plt.hist(x=boot_mean, bins='auto', color='#0504aa', alpha=0.7, rwidth=0.85)
	plt.grid(axis='y', alpha=0.75)
	plt.xlabel('Throughout Value')
	plt.ylabel('Frequency')
	plt.title('Bootstrapping')
	maxfreq = n.max()
	plt.ylim(ymax=np.ceil(maxfreq / 10) * 10 if maxfreq % 10 else maxfreq + 10)
	plt.savefig('Bootstr.png')

# Initiate bootstrapping by repeatdly calculating thorughput with same number of instances
def bootstrap(dname, pods):
	len_files = len(glob.glob(os.path.join(dname+str(int(pods))+'_pod', '*.csv'))) # we always test and calc from 2 diff requests
	if(len_files != 2):
		return
	thru, succ_rate, reqs, t_time = analysis.analyze_requests(dname, pods)
	shutil.rmtree(dname+str(int(pods))+'_pod')
	thruls = []
	thruls.append(thru)
	if os.path.exists("bootdata.txt"):
		with open("bootdata.txt", "rb") as fp:
			thr = pickle.load(fp)
			for i in range(len(thr)):
				thruls.append(thr[i])
		with open("bootdata.txt", "wb") as fp:
			pickle.dump(thruls, fp)
		print("There are "+str(len(thruls))+" throughput values ready for bootstrapping. Do you need more?")
		user = input('y / n')
		if user == 'y':
			return
		elif user == 'n':
			bootstrapping(thruls)
	else:
		with open("bootdata.txt", "wb") as fp:
			pickle.dump(thruls, fp)

# Monitoring with a 30 sec window. Update the requests (r1, r2, r3) to correct prometheus endpoint.
def monitor():
	t1 = int(time.time())
	t1 = t1 - 20
	t2 = t1 - 30
	x = datetime.datetime.fromtimestamp(t2)
	data = pd.DataFrame({'Date':[str(x)]})

	data['Date'] = pd.to_datetime(data['Date'])
	data['Time'],data['Date']= data['Date'].apply(lambda x:x.time()), data['Date'].apply(lambda x:x.date())

	r1 = requests.get("(link_to_pods_monitor)&start="+str(t2)+"&end="+str(t1)+"&step=10",
				auth=('user', 'password'))
	r2 = requests.get("(link_to_cpu_monitor)&start="+str(t2)+"&end="+str(t1)+"&step=10",
				auth=('user', 'password'))
	r3 = requests.get("(link_to_mem_monitor)&start="+str(t2)+"&end="+str(t1)+"&step=10",
				auth=('user', 'password'))

	val1 = r1.json()
	val2 = r2.json()
	val3 = r3.json()
	#print(val1)
	Pods = float(val1["data"]["result"][0]["values"][1][1])
	cpu = float("%.4f" % round(float(val2["data"]["result"][0]["values"][1][1]),4))
	Memory = float("%.4f" % round(float(val3["data"]["result"][0]["values"][1][1])/1000000, 4))
	Time = data['Time'][0]
	
	return Time, Pods, cpu, Memory
		
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Testing rules for specific pods. Very first test should be with 1 pod and 20 requests. "
					"The user may specify min and max duration of the tests else each tests will run between 2 to 4 minutes.")
	parser.add_argument('--requests', help='Enter the number of requests', required=True)
	parser.add_argument('--ftest', help='Select y if this is the first test with only 1 pod', default='n')
	parser.add_argument('--mint', help='Enter the desired minimum time for every tests', default='2')
	parser.add_argument('--maxt', help='Enter the desired maximum time for every tests', default='4')
	parser.add_argument('--boot', help='Do you want to bootstrap the result?', default='n')
	args = parser.parse_args()
	print("Test start!!")

	runtest(args.requests, args.ftest, int(args.mint), int(args.maxt), args.boot)

	sys.exit(0)
