# This code is Copyright 2014-2017 by Pier Carlo Chiodi.
# See full license in LICENSE file.

import json
try:
    import signal
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
except:
    pass
import requests
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

from errors import P2ESError

def http(CONFIG, url, method="GET", data=None):
    auth = None
    if CONFIG['ES_AuthType'] != 'none':
        if CONFIG['ES_AuthType'] == 'basic':
            auth = HTTPBasicAuth(CONFIG['ES_UserName'], CONFIG['ES_Password'])
        elif CONFIG['ES_AuthType'] == 'digest':
            auth = HTTPDigestAuth(CONFIG['ES_UserName'], CONFIG['ES_Password'])
        else:
            raise P2ESError(
                'Unexpected authentication type: {0}'.format(CONFIG['ES_AuthType'])
            )

    headers = {'Content-Type': 'application/x-ndjson'}

    if method == "GET":
        return requests.get(url, auth=auth, headers=headers)
    elif method == "POST":
        return requests.post(url, auth=auth, data=data, headers=headers)
    elif method == "PUT":
        return requests.put(url, auth=auth, data=data, headers=headers)
    elif method == "HEAD":
        return requests.head(url, auth=auth, headers=headers)
    else:
        raise Exception("Method unknown: {0}".format(method))

# Sends data to ES.
# Raises exceptions: yes.
def send_to_es(CONFIG, index_name, data):
    # HTTP bulk insert toward ES

    url = '{0}/{1}/{2}/_bulk'.format(
        CONFIG['ES_URL'],
        index_name,
        CONFIG['ES_Type']
    )

    try:
        http_res = http(CONFIG, url, method="POST", data=data)
    except Exception as e:
        raise P2ESError(
            'Error while executing HTTP bulk insert on {0} - {1}'.format(
                index_name, str(e)
            )
        )

    # Interpreting HTTP bulk insert response
    if http_res.status_code != 200:
        raise P2ESError(
            'Bulk insert on {0} failed - '
            'HTTP status code = {1} - '
            'Response {2}'.format(
                index_name, http_res.status_code, http_res.text
            )
        )

    try:
        json_res = http_res.json()
    except Exception as e:
        raise P2ESError(
            'Error while decoding JSON HTTP response - '
            '{0} - '
            'first 100 characters: {1}'.format(
                str(e),
                http_res.text[:100],
            )
        )

    if json_res['errors']:
        raise P2ESError(
            'Bulk insert on {0} failed to process '
            'one or more documents'.format(index_name)
        )

# Checks if index_name exists.
# Returns: True | False.
# Raises exceptions: yes.
def does_index_exist(index_name, CONFIG):
    url = '{0}/{1}'.format(CONFIG['ES_URL'], index_name)

    try:
        status_code = http(CONFIG, url, method="HEAD").status_code
        if status_code == 200:
            return True
        if status_code == 404:
            return False
        raise Exception("Unexpected status code: {0}".format(status_code))
    except Exception as err:
        raise P2ESError(
            'Error while checking if {0} index exists: {1}'.format(
                index_name, str(err)
            )
        )

# Creates index 'index_name' using template given in config.
# Raises exceptions: yes.
def create_index(index_name, CONFIG):

    # index already exists?
    if does_index_exist(index_name, CONFIG):
        return

    # index does not exist, creating it
    tpl_path = '{0}/{1}'.format(CONFIG['CONF_DIR'], CONFIG['ES_IndexTemplateFileName'])

    try:
        with open(tpl_path, "r") as f:
            tpl = f.read()
    except Exception as e:
        raise P2ESError(
            'Error while reading index template from file {0}: {1}'.format(
                tpl_path, str(e)
            )
        )

    url = '{0}/{1}'.format(CONFIG['ES_URL'], index_name)

    last_err = None
    try:
        # using PUT
        http_res = http(CONFIG, url, method="PUT", data=tpl)
    except Exception as e1:
        last_err = "Error using PUT method: {0}".format(str(e1))
        # trying the old way
        try:
            http_res = http(CONFIG, url, method="POST", data=tpl)
        except Exception as e2:
            # something went wrong: does index exist anyway?
            last_err += " - "
            last_err += "Error using old way: {0}".format(str(e2))
            pass

    try:
        if does_index_exist(index_name, CONFIG):
            return
    except:
        pass

    err = "An error occurred while creating index {0} from template {1}: "
    if last_err:
        err += last_err
    else:
        err += "error unknown"
    raise P2ESError(err.format(index_name, tpl_path))
