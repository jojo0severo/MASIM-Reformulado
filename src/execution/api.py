"""This module is the entry point for all the calls that the simulation will receive, all the validations and controls
are done here. It represents the server of the simulation and also the step controller.

Note: any changes on the control functions must be done carefully."""

import os
import sys
import json
import time
import queue
import signal
import zipfile
import pathlib
import requests
import multiprocessing
from glob import glob
from multiprocessing import Queue
from flask_socketio import SocketIO
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_restful import Api
from src.execution.communication.controllers.controller import Controller
from src.execution.communication.helpers import json_formatter
from src.execution.simulation_engine.json_formatter import JsonFormatter
from src.execution.logger import Logger
from src.execution.monitor_engine.controllers.monitor_manager import MonitorManager
from src.execution.monitor_engine.resources.manager import SimulationManager, MatchInfoManager, MatchStepManager, record_simulation

(base_url, port, step_time, first_step_time, method, log, social_assets_timeout, secret, config_path,
 load_sim, write_sim, replay, record, agents_amount) = sys.argv[1:]

app = Flask(__name__,
            template_folder='monitor_engine/graphic_interface/templates',
            static_folder='monitor_engine/graphic_interface/static')

api = Api(app)
socket = SocketIO(app)

monitor_manager = MonitorManager()
formatter = JsonFormatter(config_path, load_sim, write_sim)
controller = Controller(agents_amount, first_step_time, secret)
every_agent_registered = Queue()
one_agent_registered_queue = Queue()
actions_queue = Queue()
request_queue = Queue()

# Events variables
initial_percepts_event = 'initial_percepts'
percepts_event = 'percepts'
end_event = 'end'
bye_event = 'bye'
error_event = 'error'
SIM_NOT_ON = 'Simulation is not online.'
ERROR = 'Error.'


@app.after_request
def after_request(response):
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.route('/')
def monitor():
    return render_template('index.html')


@app.route('/start_connections', methods=['POST'])
def start_connections():
    """Starts the API as entry point, before calling this functions the API will only answer that the simulation
    is not online.

    It also starts processes that will handle the first step cycle. The first step cycle can be completed in some
    different ways:

    1 - All the agents connected at once: This is the expected condition for the simulation to start running, after all
    the agents connect to it, the steps engine will proceed.

    2 - Less than the total of agents connected and the time ended: It is not the perfect scenario, but is possible. If
    just one of five agents connects to the simulation it will wait for the time to end, if it ends, the steps engine
    will proceed with only that agent connected.

    3 - No agent connected and the time ended: This is the worst scenario possible for the time, if no agent is connected
    than the simulation will never start.

    4 - The user pressed any button: This is the scenario where the user has the full control of the start, it will only
    start the steps engine when the user allows it.

    Note: This endpoint must be called from the simulation, it is not recommended to the user to call it on his own."""

    Logger.normal('Start connections')

    try:
        valid, message = controller.do_internal_verification(request)

        if not valid:
            return jsonify(message=f'This endpoint can not be accessed. {message}')

        if message['back'] != 1:
            controller.set_started()

            if method == 'time':
                multiprocessing.Process(target=first_step_time_controller, args=(every_agent_registered,),
                                        daemon=True).start()

            else:
                multiprocessing.Process(target=first_step_button_controller, daemon=True).start()

        else:
            multiprocessing.Process(target=first_step_time_controller, args=(one_agent_registered_queue,),
                                    daemon=True).start()

        controller.start_timer()

        return jsonify('')

    except json.JSONDecodeError:
        msg = 'This endpoint can not be accessed.'
        return jsonify(message=msg)


def first_step_time_controller(ready_queue):
    """Waits for either all the agents connect or the time end.

    If all the agents connect, it will start the steps engine and run the simulation with them.
    If some of the agents does not connect it will call the start_connections endpoint and retry."""

    agents_connected = False

    try:
        if int(agents_amount) > 0:
            agents_connected = ready_queue.get(block=True, timeout=int(first_step_time))

        else:
            agents_connected = True

    except queue.Empty:
        pass

    if not agents_connected:
        requests.post(f'http://{base_url}:{port}/start_connections', json={'secret': secret, 'back': 1})

    else:
        requests.get(f'http://{base_url}:{port}/start_step_cycle', json={'secret': secret})

    os.kill(os.getpid(), signal.SIGTERM)


def first_step_button_controller():
    """Wait for the user to press any button, the recommended is 'Enter', but there are no restrictions."""

    sys.stdin = open(0)
    Logger.normal('When you are ready press "Enter"')
    sys.stdin.read(1)

    requests.get(f'http://{base_url}:{port}/start_step_cycle', json=secret)


@app.route('/start_step_cycle', methods=['GET'])
def start_step_cycle():
    """Start the steps engine and notify the agents that are connected to it that the simulation is starting.

    Note: When this endpoint is called, the agents or social assets can only send actions to the simulation.
    Note: This endpoint must be called from the simulation, it is not recommended to the user to call it on his own."""

    valid, message = controller.do_internal_verification(request)

    if not valid:
        return jsonify(message=f'This endpoint can not be accessed. {message}')

    controller.finish_connection_timer()

    sim_response = formatter.start()

    notify_monitor(initial_percepts_event, sim_response)
    notify_monitor(percepts_event, sim_response)
    notify_actors(percepts_event, sim_response)

    multiprocessing.Process(target=step_controller, args=(actions_queue, 1), daemon=True).start()

    return jsonify('')


@app.route('/connect_agent', methods=['POST'])
def connect_agent():
    """Connect the agent.

    If the agent is successfully connected, the simulation will return its token, any errors, it will return the error
    message and the corresponding status."""

    response = {'status': 1, 'result': True, 'message': ERROR}
    connecting_agent = True

    if controller.processing_asset_request():
        Logger.normal('Try to connect a social asset.')
        status, message = controller.do_social_asset_connection(request)
        connecting_agent = False

    else:
        Logger.normal('Try to connect a agent.')
        status, message = controller.do_agent_connection(request)

    if status != 1:
        if connecting_agent:
            Logger.error(f'Error to connect the agent: {message}')
        else:
            Logger.error(f'Error to connect the social asset: {message}')

        response['status'] = status
        response['result'] = False
    else:
        if connecting_agent:
            Logger.normal('Agent connected.')
        else:
            Logger.normal('Social asset connected.')

    response['message'] = message

    return jsonify(response)


@socket.on('register_agent')
def register_agent(msg):
    """Connect the socket of the agent.

    If no errors found, the agent information is sent to the engine and it will create its own object of the agent.

    Note: The agent must be registered to connect the socket."""

    response = {'type': 'initial_percepts', 'status': 0, 'result': False, 'message': ERROR}
    registering_agent = True

    if controller.processing_asset_request():
        registering_agent = False
        Logger.normal('Try to register and connect the social asset socket.')
        status, message = controller.do_social_asset_registration(msg, request.sid)
    else:
        Logger.normal('Try to register and connect the agent socket.')
        status, message = controller.do_agent_registration(msg, request.sid)

    if status == 1:
        try:
            if not registering_agent:
                main_token = message[0]
                token = message[1]
                sim_response = formatter.connect_social_asset(main_token, token)

                if sim_response['status'] == 1:
                    Logger.normal('Social asset socket connected.')

                    response['status'] = 1
                    response['result'] = True
                    response['message'] = 'Social asset successfully connected'

                    if controller.check_requests():
                        request_queue.put(True)

                    response.update(sim_response)
                    send_initial_percepts(token, response)

                else:
                    Logger.error(f'Error to connect the social asset socket: {message}')

                    response['status'] = sim_response['status']
                    response['message'] = sim_response['message']
            else:
                sim_response = formatter.connect_agent(message)

                if sim_response['status'] == 1:
                    Logger.normal('Agent socket connected.')

                    response['status'] = 1
                    response['result'] = True
                    response['message'] = 'Agent successfully connected.'

                    response.update(sim_response)

                    if controller.agents_amount == len(controller.manager.agents_sockets_manager.get_tokens()):
                        every_agent_registered.put(True)

                    one_agent_registered_queue.put(True)

                    send_initial_percepts(message, response)

                else:
                    Logger.error(f'Error to connect the agent socket: {message}')

                    response['status'] = sim_response['status']
                    response['message'] = sim_response['message']

        except requests.exceptions.ConnectionError:
            response['status'] = 6
            msgs = SIM_NOT_ON
            response['message'] = msgs

    else:
        Logger.error(f'Unknown error: {message}')
        response['status'] = status
        response['message'] = message

    return jsonify(0)


@app.route('/finish_step', methods=['GET'])
def finish_step():
    """Finish each step of the simulation.

    Every time the simulation finished one step, all the actions sent are processes by the engine and
    the agents and social assets are notified if the simulation ended, their actions results or if the
    simulation restarted.
    Internal errors at the engine of the API will stop the system to prevent of running hundreds of steps
    to find that on step 12 the simulation had an error and all the next steps were not executed properly.

    Note: When the engine is processing the actions, the agents or social assets can not send any action.
    Note: This endpoint must be called from the simulation, it is not recommended to the user to call it on his own."""

    Logger.normal('Preparing the actions to send.')

    valid, message = controller.do_internal_verification(request)

    if not valid:
        return jsonify(message=f'This endpoint can not be accessed. {message}')

    try:
        controller.set_processing_actions()
        tokens_actions_list = [*controller.manager.get_actions('agent'),
                               *controller.manager.get_actions('social_asset')]

        Logger.normal('Send the actions for the simulation.')
        sim_response = formatter.do_step(tokens_actions_list)
        Logger.normal('Receive the actions results from the simulation.')
        controller.manager.clear_workers()

        if sim_response['status'] == 0:
            Logger.critical('An internal error occurred. Shutting down...')
            notify_monitor(error_event, {'message': 'An internal error occurred. Shutting down...'})

            multiprocessing.Process(target=auto_destruction, daemon=True).start()

        if sim_response['message'] == 'Simulation finished.':
            Logger.normal('End of the simulation, preparer to restart.')

            can_restart = formatter.log()

            if can_restart['status'] == 1:
                sim_response = formatter.restart()
            else:
                sim_response = formatter.match_report()

            notify_monitor(end_event, sim_response['report'])
            notify_actors(end_event, sim_response['report'])

            if sim_response['status'] == 0:
                Logger.normal('No more map to run, finishing the simulation...')

                sim_response = formatter.simulation_report()

                notify_monitor(bye_event, sim_response)
                notify_actors(bye_event, sim_response)

                multiprocessing.Process(target=auto_destruction, daemon=True).start()

            else:
                Logger.normal('Restart the simulation.')

                controller.clear_social_assets(sim_response['assets_tokens'])
                controller.new_match()

                notify_monitor(initial_percepts_event, sim_response['initial_percepts'])
                notify_actors(initial_percepts_event, sim_response['initial_percepts'])
                notify_monitor(percepts_event, sim_response['percepts'])
                notify_actors(percepts_event, sim_response['percepts'])

                controller.set_processing_actions()
                multiprocessing.Process(target=step_controller, args=(actions_queue, 1), daemon=True).start()

        else:
            controller.set_processing_actions()
            notify_monitor(percepts_event, sim_response)

            if sim_response['status'] == 2:
                Logger.normal('Open connections for the social assets.')

                controller.start_social_asset_request(sim_response)
                multiprocessing.Process(target=step_controller, args=(request_queue, 2), daemon=True).start()

            else:
                notify_actors(percepts_event, sim_response)
                Logger.normal('Wait all the agent send yours actions.')

                multiprocessing.Process(target=step_controller, args=(actions_queue, 1), daemon=True).start()

    except requests.exceptions.ConnectionError:
        Logger.critical('Error to process the agents actions.')

    return jsonify(0)


@app.route('/handle_response', methods=['GET'])
def handle_response():
    Logger.normal('Handle the agent response after try to connect the social asset.')

    tokens = controller.get_social_assets_tokens()

    sim_response = formatter.finish_social_asset_connections(tokens)

    response = controller.format_actions_result(sim_response)
    notify_actors(percepts_event, response)
    controller.finish_assets_connections()

    multiprocessing.Process(target=step_controller, args=(actions_queue, 1), daemon=True).start()

    return jsonify(0)


def step_controller(ready_queue, status):
    """Wait for all the agents to send their actions or the time to end either one will cause the method to call
    finish_step."""

    if status == 2:
        try:
            ready_queue.get(block=True, timeout=int(social_assets_timeout))

        except queue.Empty:
            pass
    else:
        try:
            if int(agents_amount) > 0:
                ready_queue.get(block=True, timeout=int(step_time))

        except queue.Empty:
            pass

    try:
        if status == 2:
            requests.get(f'http://{base_url}:{port}/handle_response', json={'secret': secret})
        else:
            requests.get(f'http://{base_url}:{port}/finish_step', json={'secret': secret})

    except requests.exceptions.ConnectionError:
        pass

    os.kill(os.getpid(), signal.SIGTERM)


@socket.on('send_action')
def send_action_temp(msg):
    """Receive all the actions from the agents or social assets.

        Note: The actions are stored and only used when the step is finished and the simulation process it."""

    response = {'status': 1, 'result': True, 'message': ERROR}
    status, message = controller.do_action(msg)

    if status != 1:
        Logger.error('Error to storage the action received.')

        response['status'] = status
        response['result'] = False

    else:
        every_socket = controller.manager.get_all('socket')
        tokens_connected_size = len([*every_socket[0], *every_socket[1]])
        agent_workers_size = len(controller.manager.get_workers('agent'))
        social_asset_workers_size = len(controller.manager.get_workers('social_asset'))
        workers = agent_workers_size + social_asset_workers_size

        Logger.normal(f'Action received: {workers} of {tokens_connected_size}.')

        if tokens_connected_size == workers:
            Logger.normal('All actions received.')

            actions_queue.put(True)

    response['message'] = message


@socket.on('disconnect_registered_agent')
def disconnect_registered_agent(msg):
    """Disconnect the agent.

    The agent is removed from the API and will not be able to connect of send actions to it."""

    response = {'status': 0, 'result': False, 'message': ERROR}

    status, message = controller.do_agent_socket_disconnection(msg)

    if status == 1:
        try:
            sim_response = formatter.disconnect_agent(message)

            if sim_response['status'] == 1:
                response['status'] = 1
                response['result'] = True
                response['message'] = 'Agent successfully disconnected.'

            else:
                response['message'] = sim_response['message']

        except json.decoder.JSONDecodeError:
            response['message'] = 'An internal error occurred at the simulation.'

        except requests.exceptions.ConnectionError:
            msgs = SIM_NOT_ON
            response['message'] = msgs

    Logger.normal(f'Disconnect a agent, message: {message}')

    return json.dumps(response, sort_keys=False)


@socket.on('disconnect_registered_asset')
def disconnect_registered_asset(msg):
    """Disconnect the social asset.

    The social asset is removed from the API and will not be able to connect of send actions to it."""

    response = {'status': 0, 'result': False, 'message': ERROR}

    status, message = controller.do_social_asset_socket_disconnection(msg)

    if status == 1:
        try:
            sim_response = formatter.disconnect_social_asset(message)

            if sim_response['status'] == 1:
                response['status'] = 1
                response['result'] = True
                response['message'] = 'Social asset successfully disconnected.'

            else:
                response['message'] = sim_response['message']

        except json.decoder.JSONDecodeError:
            response['message'] = 'An internal error occurred at the simulation.'

        except requests.exceptions.ConnectionError:
            msgs = SIM_NOT_ON
            response['message'] = msgs

    return json.dumps(response, sort_keys=False)


@app.route('/download', methods=['GET'])
def download_logs():
    log_file_name = 'logs.zip'
    full_path = pathlib.Path(__file__).parents[2]
    print(str((full_path / log_file_name).absolute()))
    try:
        os.remove(str((full_path / log_file_name).absolute()))
    except FileNotFoundError:
        pass

    path = formatter.save_logs() / '*'

    zip_obj = zipfile.ZipFile(log_file_name, 'w')

    for file in glob(str(path.absolute())):
        if '/' in str(file):
            filename = '/'.join(file.split('/')[-2:])
        else:
            filename = '\\'.join(file.split('\\')[-2:])

        zip_obj.write(file, filename)

    zip_obj.close()

    return send_from_directory(directory=str(full_path.absolute()), filename=log_file_name, cache_timeout=0)


def send_initial_percepts(token, info):
    """Send the initial percepts for the agent informed.

    The message contain the agent and map percepts."""

    room = controller.manager.get(token, 'socket')
    response = json_formatter.initial_percepts_format(info, token)
    socket.emit(initial_percepts_event, response, room=room)


def notify_monitor(event, response):
    """ Update data in the monitor."""

    Logger.normal('Updating monitor.')

    if event == initial_percepts_event:
        info = json_formatter.initial_percepts_monitor_format(response)
        monitor_manager.add_match(info)

    elif event == percepts_event:
        info = json_formatter.percepts_monitor_format(response)
        match = controller.get_current_match()
        if monitor_manager.check_match_id(match):
            monitor_manager.add_match_step(match, info)

    elif event == end_event:
        info = json_formatter.end_monitor_format(response)
        match = controller.get_current_match()
        monitor_manager.set_match_report(match, info)

    elif event == bye_event:
        info = json_formatter.end_monitor_format(response)
        monitor_manager.set_sim_report(info)

        if record:
            record_simulation()

    else:
        Logger.error('Event type in "notify monitor" not found.')


def notify_actors(event, response):
    """Notify the agents and social assets through sockets.

    Each agent and each social asset has its own message related.

    Note: If an unknown event name is given, the simulation will stop because it was almost certainly caused by
    internal errors."""

    Logger.normal('Notifying the agents.')

    tokens = [*controller.manager.agents_sockets_manager.get_tokens(),
              *controller.manager.assets_sockets_manager.get_tokens()]
    room_response_list = []

    for token in tokens:
        if event == initial_percepts_event:
            info = json_formatter.initial_percepts_format(response, token)

        elif event == percepts_event:
            info = json_formatter.percepts_format(response, token)

        elif event == end_event:
            info = json_formatter.end_format(response, token)

        elif event == bye_event:
            info = json_formatter.bye_format(response, token)

        else:
            Logger.error('Wrong event name. Possible internal errors.')
            info = json_formatter.event_error_format('Error in API.')

        room = controller.manager.get(token, 'socket')
        room_response_list.append((room, json.dumps(info)))

    for room, agent_response in room_response_list:
        socket.emit(event, agent_response, room=room)


@app.route('/call_service', methods=['GET'])
def calculate_route():
    """Send a request for the simulator to calculate a route between the coord given."""

    response = {'status': 0, 'result': False, 'message': ''}

    if not controller.simulation_started():
        response['message'] = 'The simulator has not started yet.'

    else:
        status, message = controller.check_service_request(request)

        if status == 1:
            sim_response = formatter.calculate_route(request.get_json(force=True)['parameters'])

            if sim_response['status'] == 1:
                response['status'] = 1
                response['result'] = True
                response['response'] = sim_response['response']
            else:
                response['message'] = sim_response['message']
        else:
            response['message'] = message

    return jsonify(response)


@app.route('/terminate', methods=['GET'])
def terminate():
    """Terminate the process that runs the API.

    Note: This endpoint must be called from the simulation, it is not recommended to the user to call it on his own."""

    valid, message = controller.do_internal_verification(request)
    msg = 'This endpoint can not be accessed.'
    if not valid:
        
        return jsonify(message=msg)

    if 'back' not in message:
        return jsonify(message=msg)

    if message['back'] == 0:
        multiprocessing.Process(target=auto_destruction, daemon=True).start()
    else:
        socket.stop()
        os.kill(os.getpid(), signal.SIGTERM)

    return jsonify('')


def auto_destruction():
    """Wait one second and then call the terminate endpoint."""

    time.sleep(1)
    try:
        requests.get(f'http://{base_url}:{port}/terminate', json={'secret': secret, 'back': 1})
    except requests.exceptions.ConnectionError:
        pass

    os.kill(os.getpid(), signal.SIGTERM)


def run():
    if replay:
        sim_args = {'simulation_config': None, 'to_record': None, 'replay_file_name': replay}

    else:
        sim_args = {
            'simulation_config': dict(
                simulation_url=f'http://{base_url}:{port}',
                api_url=f'http://{base_url}:{port}',
                max_agents=agents_amount,
                first_step_time=first_step_time,
                step_time=step_time,
                social_asset_timeout=social_assets_timeout
            ), 'to_record': record}

    api.add_resource(SimulationManager,
                     '/simulator/info/<string:id_attribute>',
                     endpoint='sim_info',
                     resource_class_kwargs=sim_args)

    api.add_resource(MatchStepManager,
                     '/simulator/match/<int:match>/step',
                     '/simulator/match/<int:match>/step/<int:step>',
                     endpoint='step')

    api.add_resource(MatchInfoManager,
                     '/simulator/match/<int:match>/info/<string:id_attribute>',
                     endpoint='match')

    app.config['SECRET_KEY'] = secret
    app.config['JSON_SORT_KEYS'] = False
    Logger.normal(f'Serving on http://{base_url}:{port}')
    socket.run(app=app, host=base_url, port=port)
