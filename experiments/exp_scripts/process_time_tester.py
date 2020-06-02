import os
import signal
import shutil
import time
import subprocess
import pathlib
import socketio
import requests
import json
import sys


class TestTime:
    def __init__(self, action):
        self.action = action
        
        self.root = str(pathlib.Path(__file__).resolve().parents[2])
        self.temp_config = '/experiments/temp/util/temp-config.json'
        self.default_config = '/experiments/temp/util/default-config.json'
        self.api_path = self.root + '/experiments/temp/util/fake_api.py'
        self.reports_folder = '/experiments/temp/reports'
        self.sim_path = self.root + '/src/execution/simulation.py'
        self.exp_name = 'PROCESS_TIME_SEARCH'

        self.base_url = sys.argv[1]
        self.sim_port = 8910
        self.api_port = 12345
        self.secret = 'temp'
        self.sim_url = f'http://{self.base_url}:{self.sim_port}'
        self.api_url = f'http://{self.base_url}:{self.api_port}'
        self.sim_command = ['python3', self.sim_path, self.root + self.temp_config, self.base_url, str(self.sim_port), str(self.api_port), 'true', self.secret]
        self.api_command = ['python3', self.api_path, self.base_url, str(self.api_port), self.secret]

        self.socket = socketio.Client()
        self.socket.on('sim_started', self.finish)
        self.sim_started = False
        self.actions = []

        self.args = [int(n) for n in sys.argv[1:]]
        self.complexity_experiments = self.args[:int(len(self.args) / 2)]
        self.agents_experiments = self.args[int(len(self.args) / 2):]

        self.results = []
        self.default_steps = 0

        shutil.copy2(self.root + self.default_config, self.root + self.temp_config)
        
    @staticmethod
    def get_current_time():
        return int(round(time.time() * 1000))
    
    def save_results(self, agents_amount, prob):
        path = f'{self.root}{self.reports_folder}/PROCESS_TIME%SEARCH%{str(agents_amount)}_{str(prob)}.csv'
    
        with open(path, 'w+') as report:
            for e in self.results:
                report.write(str(e) + '\n')
                
    def finish(self, *args):
        self.sim_started = True
    
    def set_environment_steps(self, agents_amount, prob):    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Setting the environment.')
        with open(self.root + self.default_config, 'r') as config:
            content = json.loads(config.read())
    
        content['generate']['flood']['probability'] = prob
        content['agents']['drone']['amount'] = agents_amount
    
        with open(self.root + self.temp_config, 'w') as config:
            config.write(json.dumps(content, sort_keys=False, indent=4))
    
    def start_processes(self, agents_amount, prob):
        self.sim_started = False
    
        api_null = open(os.devnull, 'w')
        api_proc = subprocess.Popen(self.api_command, stdout=api_null, stderr=subprocess.STDOUT)
    
        connected = False
        while not connected:
            try:
                self.socket.connect(self.api_url)
                connected = True
            except Exception:
                time.sleep(1)
    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Start simulator process.')
        sim_proc = subprocess.Popen(self.sim_command)
    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Waiting for the simulation start...')
    
        while not self.sim_started:
            time.sleep(1)
    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Simulation started, connecting the agents...')
        self.connect_agents(agents_amount)
    
        requests.post(self.sim_url + '/start', json={'secret': self.secret})
    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Agents connected, processing steps...')
        step = 0
        while step in range(self.default_steps):
            old_time = self.get_current_time()
            requests.post(self.sim_url+'/do_actions', json={'actions': self.actions, 'secret': self.secret})
            new_time = self.get_current_time()
            self.results.append(new_time - old_time)
            step += 1
            
        self.save_results(agents_amount, prob)
        self.results.clear()
        self.actions.clear()
        self.socket.disconnect()
    
        self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Simulation finished, killing all processes...')
    
        api_proc.kill()
        sim_proc.kill()
    
    @staticmethod
    def log(exp, message):
        print(f'[{exp}] ## {message}')
    
    def connect_agents(self, agents_amount):
        for agent in range(agents_amount):
            token = f'temp{agent}'
            requests.post(self.sim_url+'/register_agent', json={'token': token, 'secret': self.secret})
            self.actions.append({'token': token, 'action': self.action, 'parameters': []})
    
    def start_experiments(self):
        for agents_amount in self.agents_experiments:
            for prob in self.complexity_experiments:
                self.log(f'{self.exp_name}_{agents_amount}_{prob}', 'Start new experiment.')
    
                self.set_environment_steps(agents_amount, prob)
                self.start_processes(agents_amount, prob)
                time.sleep(2)

        print('[FINISHED] ## Finished all experiments')
        os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
    # TestTime('searchSocialAsset').start_experiments()
    TestTime('pass').start_experiments()
