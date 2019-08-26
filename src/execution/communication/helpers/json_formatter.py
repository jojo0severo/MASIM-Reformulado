"""This module formats the different events to send to the agents and social assets.

Note: The response does not have agent or social asset as key until they are processed."""


def simulation_started_format(response, token):
    """Build the response for the token given in the parameters.

    It will loop through all the actors named on the response until if finds the one that matches the token.

    :param response: Response from the engine.
    :param token: Current token."""

    info = {'status': 0, 'result': False, 'environment': {}, 'message': '', 'type': 'percepts'}

    if response:
        if response['status']:
            info['status'] = response['status']
            info['result'] = True

            found_index = 0
            for idx, actor in enumerate(response['actors']):
                if actor['token'] == token:
                    if 'role' in actor:
                        info['agent'] = actor
                    else:
                        info['agent'] = actor
                    found_index = idx
                    break

            if 'agent' not in info and 'social_asset' not in info:
                return event_error_format('Actor not found in response. ')

            response['actors'].pop(found_index)
            info['environment'] = response['environment']

        info['message'] = response['message']

        return info

    else:
        return event_error_format('Empty simulation response. ')


def simulation_ended_format(response, token):
    """Build the response for the token given in the parameters.

    :param response: Response from the engine.
    :param token: Current token
    """

    info = {'status': 0, 'result': False, 'message': '', 'type': 'bye', 'simulation_report': {}}

    if response:
        if response['status']:
            info['status'] = response['status']
            info['result'] = True

        info['message'] = response['message']
        info['simulation_report'] = response['report'][token]

        return info

    else:
        return event_error_format('Empty response. ')


def action_results_format(response, token):
    """Build the response for the token given in the parameters.

    It will loop through all the actors named on the response until if finds the one that matches the token.

    :param response: Response from the engine.
    :param token: Current token."""

    info = {'status': 0, 'result': False, 'environment': {}, 'message': '', 'type': 'percepts'}

    if response:
        if response['status']:
            info['status'] = response['status']
            info['result'] = True

            found_index = 0
            for idx, actor in enumerate(response['actors']):
                if 'agent' in actor:
                    if actor['agent']['token'] == token:
                        info['agent'] = actor['agent']
                        info['message'] = actor['message']
                        found_index = idx
                        break
                else:
                    if actor['social_asset']['token'] == token:
                        info['agent'] = actor['social_asset']
                        info['message'] = actor['message']
                        found_index = idx
                        break

            if 'agent' not in info and 'social_asset' not in info:
                return event_error_format('Actor not found in response. ')

            response['actors'].pop(found_index)
            info['environment'] = response['environment']

        else:
            info['message'] = response['message']

        return info

    else:
        return event_error_format('Empty simulation response. ')


def match_result_format(response, token):
    """Build the response for the token given in the parameters.

    :param response: Response from the engine.
    :param token: Current token.
    """

    return {'type': 'end', 'report': response[token]}


def event_error_format(message):
    """Build a typical error response for the agents. When this function is called, it is very probably that an internal
    error occurred."""

    return {'status': 0, 'result': False, 'environment': {}, 'message': f'{message}Possible internal error.'}

