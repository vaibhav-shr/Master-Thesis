import argparse
import sys, os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import math
import pickle
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

su_rate = []
throughput = []
n_requests = []
total_time = []
pod = []
inc_pod = []

path = os.path.dirname(os.path.realpath(__file__))

def getdata():
	if os.path.exists("data.txt"):
		with open("data.txt", "rb") as fp:
			pod = pickle.load(fp)
			return pod
	else:
		pod = [1, 10, 20]
		with open("data.txt", "wb") as fp:
			pickle.dump(pod, fp)
		return pod

def analyze(cpu, mem, thr, sr, accu, totime):
	pod = getdata()
	for p in pod:
		throu, s_rate, n_reqs, t_time = analyze_requests(path, p)
		throughput.append(throu)
		su_rate.append(s_rate)
		n_requests.append(n_reqs)
		total_time.append(t_time)
		#print(throughput)
		#print(su_rate)

		res = analyze_resource(path, p, float(cpu), float(mem))
		if res != 0:
			inc_pod.append(res)

	pod_recommender(throughput, su_rate, pod, thr, sr, inc_pod, n_requests, total_time, accu, totime)
		#print(inc_pod)

# calculates throughput and success rate
def analyze_requests(path, p):
	req = []
	com_path = path+"/"+str(p)+"_pod/"
	len_files = len(glob.glob(os.path.join(com_path, '*.csv')))

	#sort the files according to total requests to find max throughput
	for filename in glob.glob(os.path.join(com_path, '*.csv')):
		filename = os.path.basename(filename)
		req.append(int(filename.split('_')[0]))
		req.sort()
	if len(req) == 0:
		print("Please conduct tests with recommended number of pods first. Or else delete data.txt file!")
		sys.exit(0)
	reqs = req[0]
	if len(req) == 2:
		reqs = req[1]

	succ_rate = 0.0
	thru_prev = 0.0
	for i in range(len_files):
		df = pd.read_csv(com_path+str(req[i])+'_requests.csv')
		#print(str(com_path)+str(req[i])+'_requests.csv')

		df.drop(df.index[-1], inplace=True)
		tot_time = df["Average response time"] * df["# requests"]
		df["Tot_time"] = tot_time

		requests = df["# requests"][0]
		df.drop(df.index[0], inplace=True)
		t_time = (df["Tot_time"].max())/1000
		thru = float(requests/t_time) #throughput of current test with specific number of requests
		# success rate
		new_succ_rate = float(requests / req[i])
		if succ_rate == 0.0:
			succ_rate = new_succ_rate
		elif succ_rate != 0.0:
			if new_succ_rate < succ_rate:
				succ_rate = new_succ_rate

		#print("thru is "+str(thru))

		err = error(thru, thru_prev)
		#print(err)

		#if difference is between 2 tests is very less, it is saturation point for throughout.
		if err < 7.0:
			thru_prev = float(thru + thru_prev) / 2
			break

		#if difference is more and we have more files to test, we continue
		elif err > 7.0 and i < len_files - 1:
			if thru > thru_prev:
				thru_prev = thru

		#if difference is more and we dont have more files to test, we exit
		elif err > 7.0 and i == len_files - 1:
			print("Throughput with previous file was: "+str(thru_prev)+" and now is: "+str(thru)+" . Do you accept their average as final throughput?")
			user = input('y / n')
			if user == 'y':
				thru_prev = float(thru + thru_prev) / 2
				break

			print("Insufficient data for "+ str(p)+ ". Exiting!!")
			sys.exit(0)

	return thru_prev, succ_rate, reqs, t_time

#calculate difference between current and last throughput
def error(thru, thru_prev):
	if thru > thru_prev:
		err = float(((thru - thru_prev) * 100) / thru)
	else:
		err = float(((thru_prev - thru) * 100) / thru_prev)
	return err

# Identifies the resource profile
def analyze_resource(path, p, cpu, memory):
	com_path = path+"/"+str(p)+"_pod/resource/"
	req = []
	len_files = len(glob.glob(os.path.join(com_path, '*.csv')))
	for filename in glob.glob(os.path.join(com_path, '*.csv')):
		filename = os.path.basename(filename)
		#print(filename)
		req.append(int(filename.split('_')[0]))
		req.sort()

	cpu_count = 0
	cpu_flag = 0
	mem_count = 0
	mem_flag = 0
	
	for i in range(len_files):
		df = pd.read_csv(com_path+str(req[i])+'_resource.csv')
		pods = df["Pods"][0]
		t_cpu = pods * cpu
		t_mem = pods * memory
		total = len(df.index)
		#print(total)
		if mem_flag == 0:
			for j in range(total-1): #removing last entry
				#print(df["CPU"][j])
				if df["CPU"][j] >= float(0.5 * t_cpu):
					cpu_count = cpu_count + 1
			max_cpu = df["CPU"].max()
			if cpu_count >= float(0.5 * (total-1)) and cpu_flag == 0 and i == 0:# and max_cpu > float(0.85 * pods):
				cpu_flag = 1
				
			elif cpu_count >= float(0.5 * (total-1)) and cpu_flag == 1 and i == 1:
				pass
			# In previously test CPU was consumed to max but not in second
			elif cpu_count < float(0.5 * (total-1)) and cpu_flag == 1 and i == 1:
				cpu_flag = 0	
				print("Resource usage undefined for the application for "+str(pods)+" pods with "+str(req[i])+" requests.")
			# In previously test CPU was not consumed to max but did in second
			elif cpu_count >= float(0.5 * (total-1)) and cpu_flag == 0 and i ==1:	
				cpu_flag = 0
				print("Resource usage undefined for the application for "+str(pods)+" pods with "+str(req[i])+" requests.")
			elif cpu_flag == 0:
				print("Application did not reach to the CPU boundaries for "+str(pods)+" pods with "+str(req[i])+" requests")

		if cpu_flag == 0:
			for j in range(total-1):
				if df["Mem"][j] >= float(0.5 * t_mem):
					mem_count = mem_count + 1
			max_mem = df["Mem"].max()
			#print(mem_count)
			if mem_count >= float(0.5 * (total-1)) and mem_flag == 0 and i == 0:# and max_mem > float(0.85 * memory):
				mem_flag = 1
				
			elif mem_count >= float(0.5 * (total-1)) and mem_flag == 1 and i == 1:
				pass
			# In previously test memory was consumed to max but not in second	
			elif cpu_count < float(0.5 * (total-1)) and mem_flag == 1 and i == 1:
				mem_flag = 0
				print("Resource usage undefined for the application for "+str(pods)+" pods with "+str(req[i])+" requests.")
			# In previously test memory was not consumed to max but did in second	
			elif cpu_count >= float(0.5 * (total-1)) and mem_flag == 0 and i ==1:	
				mem_flag = 0
				print("Resource usage undefined for the application for "+str(pods)+" pods with "+str(req[i])+" requests.")
			elif mem_flag == 0:
				print("Application did not reach to the memory boundaries for "+str(pods)+" pods with "+str(req[i])+" requests")

	if cpu_flag == 1 and mem_flag == 0:
		print("Its a CPU intensive application for "+str(pods)+" pods")
	elif mem_flag == 1 and cpu_flag == 0:
		print("Its a memory intensive application for "+str(pods)+" pods")
	else:
		print("Resource usage undefined for the application for "+str(pods)+" pods.")
		return int(pods)

	return 0

# With all data available, this function recommends number of instance for given SLA
def pod_recommender(throughput_list, s_rate, pod, thr, sr, incorrect_pod, n_req, ttime, accu, totime):
	if len(incorrect_pod) == 3 or len(incorrect_pod) == 2:
		print("The application's reource profile is imperfect and SLAs can not be verified!")
		return
	elif len(incorrect_pod) == 1:
		diff = error(throughput[1], throughput[2])
		diff = round(diff,2)
		print("The maximum verified throughput is with 10 pods. The difference in throughputs of 10 and 20 pods is "+str(diff)+"%")
		print("The maximum throughput for this application is "+str(throughput[1]))
		return

	X_list = [list(a) for a in zip(throughput_list, s_rate)]
	Y_list = pod

	x_list = [list(a) for a in zip(thr, sr)]

	poly = PolynomialFeatures(degree=2)
	X_ = poly.fit_transform(X_list)
	X_test = poly.fit_transform(x_list)

	lg = LinearRegression()
	lg.fit(X_, Y_list)

	y_pred = lg.predict(X_test)
	if y_pred[0] < 0:
		y_pred[0] = 1
	rec_pods = math.ceil(y_pred[0])

	plt.rcParams.update({'font.size': 20})

	fig, axs = plt.subplots(4, 1, sharex=True, sharey=False)
	axs[0].plot(lg.predict(poly.fit_transform(X_list)), throughput_list, color='r', marker='o', label='throughput')
	axs[0].set(ylabel='Maximum Throughput')

	axs[1].plot(lg.predict(poly.fit_transform(X_list)), ttime, color='r', marker='o', label='Total time')
	axs[1].set(ylabel='Total Response Time (s)')

	axs[2].plot(lg.predict(poly.fit_transform(X_list)), s_rate, color='g', marker='o', label='Success rate')
	axs[2].set(ylabel='Maximum Success Rate')	

	axs[3].bar(lg.predict(poly.fit_transform(X_list)), n_req, color='r', label='Total requests')
	axs[3].set(ylabel='Number of Requests', xlabel='Number of Pods')

	for ax in axs:
		ax.set_facecolor('#edf8fd')
		ax.grid()
		ax.legend(loc='upper left')

	fig.subplots_adjust(hspace=0)
	plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible=False)
	
	fig.set_size_inches(25, 25)
	fig.set_dpi(80)

	plt.savefig('diagrams_loc.png')

	#print("The recommended number pods for your SLA is: "+str(rec_pods))
	n_time = len(ttime)
	sum_time = sum(ttime)
	avg_time = sum_time / n_time

	# If time is there and this is the first prediction, a accuracy can't be calculated (see description of accuracy in readme)
	if (totime - sum_time) > avg_time:
		if n_time == 3:
			print("The recommended number of pods for your SLA is: "+str(rec_pods))
			print("The following verification test may be conducted:")

			req = []
			for filename in glob.glob(os.path.join(path+"/1_pod/", '*.csv')):
				filename = os.path.basename(filename)
				req.append(int(filename.split('_')[0]))
				req.sort()
			rec_pods_requests = req[0] * rec_pods
			print(str(rec_pods)+" pods -----> "+str(rec_pods_requests)+" requests")
			next_req = int((rec_pods_requests / 2) + rec_pods_requests)
			print(str(rec_pods)+" pods -----> "+str(next_req)+" requests")
			Y_list.append(rec_pods)
			Y_list.sort()
			with open("data.txt", "wb") as fp:
				pickle.dump(Y_list, fp)
				pickle.dump(rec_pods, fp)
			new_folder = path+"/"+str(rec_pods)+"_pod/"
			try:
				os.mkdir(new_folder)
				os.mkdir(new_folder+"resource/")
			except OSError:
				print("Folder creation failed")

		# if this is not the first prediction we also calculate accuracy
		elif n_time > 3:
			with open("data.txt", "rb") as fp:
				pod_list = pickle.load(fp)
				last = pickle.load(fp)
			acc_err = error(rec_pods, last)
			acc_err = 100 - acc_err
			if acc_err > accu[0]:
				print("The recommended number pods for your SLA is: "+str(rec_pods)+". The accuracy being "+str(acc_err)+"%"+" for your SLA.")
				return

			print("The recommended number of pods for your SLA is: "+str(rec_pods))
			print("The following verification test may be conducted:")

			req = []
			for filename in glob.glob(os.path.join(path+"/1_pod/", '*.csv')):
				filename = os.path.basename(filename)
				req.append(int(filename.split('_')[0]))
				req.sort()
			rec_pods_requests = req[0] * rec_pods
			print(str(rec_pods)+" pods -----> "+str(rec_pods_requests)+" requests")
			next_req = int((rec_pods_requests / 2) + rec_pods_requests)
			print(str(rec_pods)+" pods -----> "+str(next_req)+" requests")
			Y_list.append(rec_pods)
			Y_list.sort()
			with open("data.txt", "wb") as fp:
				pickle.dump(Y_list, fp)
				pickle.dump(rec_pods, fp)
			new_folder = path+"/"+str(rec_pods)+"_pod/"
			try:
				os.mkdir(new_folder)
				os.mkdir(new_folder+"resource/")
			except OSError:
				print("Folder creation failed")

	# if no time left
	elif (totime - sum_time) < avg_time:
		if n_time == 3:
			print("The recommended number of pods for your SLA is: "+str(rec_pods))
			print("Due to time constraints it can not be verified")
			return

		elif n_time > 3:
			with open("data.txt", "rb") as fp:
				pod_list = pickle.load(fp)
				last = pickle.load(fp)
			acc_err = error(rec_pods, last)
			acc_err = 100 - acc_err
			if acc_err > accu[0]:
				print("The recommended number of pods for your SLA is: "+str(rec_pods)+". The accuracy being "+str(acc_err)+"%"+" for your SLA.")
			else:
				print("The recommended number of pods for your SLA is: "+str(rec_pods)+". Due to time constraints it can not be verified further.")

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Analysis of the experiments conducted and verification of the SLA."
												 "User may enter the desired accuracy and time constraints. Time constraint should be atleast 18 minutes(1080 sec) for good estimation of resources.")
	parser.add_argument('--cpu', help='Enter the cpu each pod is allocated', required=True)
	parser.add_argument('--mem', help='Enter the memory each pod is allocated in units of MB', required=True)
	parser.add_argument('--thr', help='Enter the desired throughput', type=float, required=True)
	parser.add_argument('--sr', help='Enter the desired succress rate', type=float, required=True)
	parser.add_argument('--accu', help='Enter the desired accuracy', type=float, default='95')
	parser.add_argument('--totime', help='Enter the maximum time in sec allocated for resource estimation', type=float, default='1500')
	args = parser.parse_args()

	print("Analysis start!!")
	thr = []
	thr.append(args.thr)
	sr = []
	sr.append(args.sr)
	accu = []
	accu.append(args.accu)
	totime = []
	totime.append(args.totime)
	analyze(args.cpu, args.mem, thr, sr, accu, totime)
	sys.exit(0)
