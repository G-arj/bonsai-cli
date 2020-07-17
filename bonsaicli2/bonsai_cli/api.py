"""
This file contains the API code for version 2 of the bonsai command line
"""
__author__ = "Karthik Sankara Subramanian"
__copyright__ = "Copyright 2019, Microsoft Corp."

import click
import json
import sys
import pprint

from typing import Any, Dict, Optional
from uuid import uuid4

if sys.version_info >= (3, ):
    from urllib.parse import urljoin
    from urllib.request import getproxies
else:
    from urllib import getproxies

import requests
from . import __version__
from .logger import Logger
from .aad import AADClient
from .exceptions import UsageError

_LIST_BRAINS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains"
_CREATE_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}"
_GET_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}"
_DELETE_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}"
_UPDATE_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}"

_LIST_BRAIN_VERSIONS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions"
_GET_BRAIN_VERSION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}"
_CREATE_BRAIN_VERSION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions"
_UPDATE_BRAIN_VERSION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}"
_DELETE_BRAIN_VERSION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}"

_LIST_SIM_PACKAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages"
_GET_SIM_PACKAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}"
_CREATE_SIM_PACKAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{packagename}"
_UPDATE_SIM_PACKAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}"
_DELETE_SIM_PACKAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}"

_LIST_SIM_COLLECTION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}/simulatorcollections"
_GET_SIM_COLLECTION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}/simulatorcollections/{collectionid}"
_CREATE_SIM_COLLECTION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}/simulatorcollections"
_UPDATE_SIM_COLLECTION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}/simulatorcollections/{collectionid}"
_DELETE_SIM_COLLECTION_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorpackages/{simulatorpackagename}/simulatorcollections/{collectionid}"

_LIST_EXPORTED_BRAINS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/exportedBrains"
_CREATE_EXPORTED_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/exportedBrains"
_GET_EXPORTED_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/exportedBrains/{exportedbrainname}"
_DELETE_EXPORTED_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/exportedBrains/{exportedbrainname}"
_UPDATE_EXPORTED_BRAIN_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/exportedBrains/{exportedbrainname}"

_LIST_SIM_BASE_IMAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorbaseimages"
_GET_SIM_BASE_IMAGE_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorbaseimages/{imageidentifier}"

_RESET_BRAIN_TRAINING_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}/resetTraining"
_START_BRAIN_TRAINING_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}/startTraining"
_STOP_BRAIN_TRAINING_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}/stopTraining"

_START_BRAIN_ASSESSMENT_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}/startAssessment"
_STOP_BRAIN_ASSESSMENT_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/brains/{name}/versions/{version}/stopAssessment"


_LIST_SIM_SESSIONS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorsessions?deployment_mode=neq:Hosted"
_GET_SIM_SESSIONS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorsessions/{sessionid}"
_PATCH_SIM_SESSIONS_URL_PATH_TEMPLATE = "/v2/workspaces/{workspacename}/simulatorSessions/{sessionid}"

log = Logger()

class BrainServerError(Exception):
    """
    This is thrown for any errors.
    """

    def __init__(self, exception: Any):
        self.exception = exception

    pass

def _handle_and_raise(response: requests.Response, e: Any, request_id: str):
    """
    This takes an exception and wraps it in a BrainServerError.
    :param response: The response from the server.
    :param e: The error raised by the requests call.
    """
    error_response: Any = {}

    try:
        error_dump = response.json()
    except:
        error_dump = 'Unknown server error occurred'

    try:
        error_code = 'Request failed with error code "{}"'.format(
            response.json()["error"]["code"])
    except:
        error_code = ''

    try:
        error_message = 'Error message: {}'.format(
            response.json()["error"]["message"])
    except:
        error_message = 'Request failed.'

    try:
        error_message += ' Request ID: {}'.format(request_id)
        error_message += ' Span ID: {}'.format(response.headers['SpanID'])
    except KeyError:
        pass

    try:
        error_response['errorDump'] = error_dump
        error_response['status'] = 'Failed'
        error_response['statusCode'] = response.status_code
        error_response['elapsed'] = response.elapsed
        error_response['exception'] = e
        error_response['errorCode'] = error_code
        error_response['errorMessage'] = error_message
        error_response['timeTaken'] = response.headers['x-ms-response-time']
    except KeyError:
        pass

    raise BrainServerError(error_response)

def _dict(response: Any, request_id: str):
    """
    Translates the response from the server into a dictionary. The implication
    is that the server should send back a JSON response for every REST API
    request, and if for some reason, that response is missing, it should be
    treated as an empty JSON message rather than an error. This method will
    change empty responses into empty dictionaries. Responses that are not
    formatted as JSON will raise an exception.
    :param response: The response from the server.
    :return: Dictionary form the JSON text in the response.
    """

    response_dict: Any = {}
    if response and response.text and response.text.strip():
        try:
            if(isinstance(response.json(), dict)):
                response_dict = response.json()
            else:
                response_dict = {'value': response.json()}
        except ValueError:
            pass

    try:
        status = "Succeeded" if response.ok else "Failed"
        response_dict["status"] = status
        response_dict["statusCode"] = response.status_code
        response_dict['statusMessage'] = ''
        response_dict['elapsed'] = response.elapsed
        response_dict['timeTaken'] = response.headers['x-ms-response-time']
    except KeyError:
        pass

    return response_dict

class BonsaiAPI(object):
    """
    This object is required to use the Bonsai API CLI, as it sets up the
    necessary URLs and communications for communicating with the Bonsai BRAIN
    backend.

    Errors, both client-side and server-side, are expressed as
    RuntimeError errors. The exception will contain details of the
    error, such as the failing response code and/or error message.
    """

    # constant class variable for request timeout time in seconds
    TIMEOUT = 300

    def __init__(self,
                 access_key: Optional[str] = None,
                 workspace_id: Optional[str] = None,
                 tenant_id: Optional[str] = None,
                 api_url: Optional[str] = None,
                 gateway_url: Optional[str] = None):
        """
        Initializes the API object.
        :param access_key: The access key for the user. This can be obtained from the bons.ai website.
        :param workspace_id: The name of the user.
        :param api_url: The URL to for the BRAIN REST API.
        :param ws_url: The websocket URL for the BRAIN API.
        """
        log.debug(
            'Bootstrapping the Bonsai API for user: {}'.format(workspace_id))

        if(access_key is None):
            raise ValueError("Access key is missing")

        if(workspace_id is None):
            raise ValueError("Workspace name is missing")

        if(api_url is None):
            raise ValueError("API url is missing")

        if(gateway_url is None):
            raise ValueError("Gateway url is missing")

        self._access_key = access_key
        self._workspace_id = workspace_id
        self.tenant_id = tenant_id
        self._api_url = api_url
        self._gateway_url = gateway_url
        self._user_info = self._get_user_info()
        self._session = requests.Session()
        self._session.proxies = getproxies()

    @staticmethod
    def _get_user_info():
        """ Get Information about user that will be passed into
            The 'User-Agent' header with requests """
        platform = sys.platform
        python_version = "{}.{}.{}".format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro)
        bonsai_cli_version = __version__
        user_info = "bonsai-cli/{} (python {}; {})".format(
            bonsai_cli_version, python_version, platform)
        return user_info

    def _get_headers(self):
        return {
            'Authorization': self._access_key,
            'User-Agent': self._user_info,
        }

    def _try_http_request(self,
                http_method: str,
                url: str,
                data: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, Any]] = None):
        log.debug('Sending {} request to {}'.format(http_method, url))

        req_id = str(uuid4())
        headers_out = self._get_headers()
        headers_out.update({'RequestId': str(uuid4())})

        scrubbed_headers = headers_out.copy()
        token = scrubbed_headers.get('Authorization')
        if token:
            scrubbed_headers['Authorization'] = '***{}'.format(token[-10:])
        log.debug('{} request headers:\n{}'.format(http_method,
                                                   pprint.pformat(scrubbed_headers)))

        if headers:
            headers_out.update(headers)

        try:
            if http_method == 'GET':
                response = self._session.get(url=url,
                                             headers=headers_out,
                                             timeout=self.TIMEOUT)
            elif http_method == 'DELETE':
                response = self._session.delete(url=url,
                                                allow_redirects=False,
                                                headers=headers_out,
                                                timeout=self.TIMEOUT)
            elif http_method == 'PUT':
                response = self._session.put(url=url,
                                             headers=headers_out,
                                             json=data,
                                             allow_redirects=False,
                                             timeout=self.TIMEOUT)
            elif http_method == 'POST':
                response = self._session.post(url=url,
                                              headers=headers_out,
                                              json=data,
                                              allow_redirects=False,
                                              timeout=self.TIMEOUT)
            elif http_method == 'PATCH':
                response = self._session.patch(url=url,
                                               headers=headers_out,
                                               json=data,
                                               allow_redirects=False,
                                               timeout=self.TIMEOUT)
            elif http_method == 'POST_RAW':
                response = self._session.post(url=url,
                                              headers=headers_out,
                                              data=data,
                                              allow_redirects=False,
                                              timeout=self.TIMEOUT)
            elif http_method == 'PUT_RAW':
                response = self._session.put(url=url,
                                             headers=headers_out,
                                             data=data,
                                             allow_redirects=False,
                                             timeout=self.TIMEOUT)
            else:
                raise UsageError('UNSUPPORTED HTTP REQUEST METHOD')

        except requests.exceptions.ConnectionError:
            raise BrainServerError(
                'Connection Error. Unable to connect to domain: {}. ' \
                'Request ID: {}'.format(url, req_id))
        except requests.exceptions.Timeout:
            raise BrainServerError(
                'Request to {} timed out. Current timeout is {} seconds. ' \
                'Use the --timeout/-t option to adjust the ' \
                'timeout. Request ID: {}'.format(url, self.TIMEOUT, req_id))

        try:
            response.raise_for_status()
            self._raise_on_redirect(response)
            log.debug('{} {} results:\n{}'.format(
                http_method, url, response.text))
            return _dict(response, req_id)
        except requests.exceptions.HTTPError as e:
            _handle_and_raise(response, e, req_id)

    def _http_request(self,
                http_method: str,
                url: str,
                data: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, Any]] = None,
                debug: bool = False,
                output: Optional[str] = None):
        """
        Wrapper for _try_http_request(), will switch to AAD authentication
        and retry if first attempt fails due to deprecated Bonsai credentials.
        """

        if (debug):
            click.echo('------ REQUEST ------')
            click.echo()
            click.echo('HTTP METHOD : {}'.format(http_method))
            click.echo('URL         : {}'.format(url))
            click.echo('BODY        : {}'.format(data))
            click.echo()
            click.echo()

        try:
            response = self._try_http_request(http_method, url, data, headers)
            return response
        except BrainServerError as err:
            # check error codes and switch to AAD auth if needed
            if ('BonsaiAuthDeprecated' in str(err) or
                'InvalidUseOfAccessKey' in str(err)):
                log.debug('Received BonsaiAuthDeprecated or '
                          'InvalidUseOfAccessKey from service, '
                          'switching to AAD authentication. Full error '
                          'text: {}'.format(str(err)))
                aad_client = AADClient(self.tenant_id)
                self._access_key = aad_client.get_access_token()

                return self._try_http_request(http_method, url, data, headers)
            else:
                raise err

    def _post(self, url: str, data: Optional[Dict[str, Any]] = None, debug: bool = False, output: Optional[str] = None):
        """
        Issues a POST request.
        :param url: The URL being posted to.
        :param data: Any additional data to bundle with the POST, as a
                     dictionary. Defaults to None.
        """
        return self._http_request('POST', url=url, data=data, debug=debug, output=output)

    def _patch(self, url: str, data: Optional[Dict[str, Any]] = None, debug: bool = False, output: Optional[str] = None):
        """
        Issues a PATCH request.
        :param url: The URL being patched to.
        :param data: Any additional data to bundle with the POST, as a
                     dictionary. Defaults to None.
        """
        return self._http_request('PATCH', url=url, data=data, debug=debug, output=output)

    def _put(self, url: str, data: Optional[Dict[str, Any]] = None, debug: bool = False, output: Optional[str] = None):
        """
        Issues a PUT request.
        :param url: The URL being PUT to.
        :param data: Any additional data to bundle with the POST, as a
                     dictionary. Defaults to None.
        """
        return self._http_request('PUT', url, data=data, debug=debug, output=output)

    def _get(self, url: str, debug: bool = False, output: Optional[str] = None):
        """
        Issues a GET request.
        :param url: The URL being GET from.
        """
        return self._http_request('GET', url=url, debug=debug, output=output)

    def _delete(self, url: str, debug: bool = False, output: Optional[str] = None):
        """
        Issues a DELETE request.
        :param url: The URL to DELETE.
        """
        return self._http_request('DELETE', url, debug=debug, output=output)

    def list_brains(self, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of brains for {}...'.format(self._workspace_id))

        url_path = _LIST_BRAINS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id
        )

        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def create_brain(self, name: str, display_name: str, description: Optional[str] = None, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Creating a BRAIN named {}'.format(name))
        url_path = _CREATE_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)

        data = {"name": name, "displayName": display_name, "description": description}
        return self._put(url=url, data=data, debug=debug, output=output)

    def update_brain(self, name: str, display_name: str, description: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Updating details for brain {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _UPDATE_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)

        data = {"displayName": display_name, "description": description}
        return self._patch(url=url, data=data, debug=debug, output=output)

    def get_brain(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about brain {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _GET_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def delete_brain(self, name: str, workspace: Optional[str] = None, debug: bool = False):
        log.debug('Deleting a brain named {}'.format(name))
        url_path = _DELETE_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)
        return self._delete(url=url, debug=debug)

    def create_brain_version(self, name: str, source_version: int, description: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Creating a new version of BRAIN {} from source version {}'.format(name, source_version))
        url_path = _CREATE_BRAIN_VERSION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)

        data = {"sourceVersion": source_version, "description": description}
        return self._post(url=url, data=data, debug=debug, output=output)

    def list_brain_versions(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of brains for {}...'.format(self._workspace_id))
        url_path = _LIST_BRAIN_VERSIONS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def get_brain_version(self, name: str, version: int, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about brain version {} of brain {} in workspace {}...'.format(name, version, self._workspace_id))
        url_path = _GET_BRAIN_VERSION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name,
            version = version
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def update_brain_version_details(self, name: str, version: int, description: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Updating details for brain {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _UPDATE_BRAIN_VERSION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name,
            version = version
        )
        url = urljoin(self._api_url, url_path)

        data = {"description": description}
        return self._patch(url=url, data=data, debug=debug, output=output)

    def update_brain_version_inkling(self, name: str, version: int, inkling: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Updating inkling for brain {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _UPDATE_BRAIN_VERSION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name = name,
            version = version
        )
        url = urljoin(self._api_url, url_path)

        data = {"inkling": inkling}
        return self._patch(url=url, data=data, debug=debug, output=output)

    def delete_brain_version(self, name: str, version: int, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Deleting version {} of brain {}'.format(version, name))
        url_path = _DELETE_BRAIN_VERSION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )
        url = urljoin(self._api_url, url_path)
        return self._delete(url=url, debug=debug, output=output)

    def create_sim_package(self,
                           name: str,
                           image_path: str,
                           start_instance_count: int,
                           cores_per_instance: float,
                           memory_in_gb_per_instance: float,
                           display_name: Optional[str] = None,
                           description: Optional[str] = None,
                           os_type: Optional[str] = None,
                           package_type: Optional[str] = None,
                           min_instance_count: int = 1,
                           max_instance_count: int = 1,
                           auto_scale: bool = False,
                           auto_terminate: bool = True,
                           workspace: Optional[str] = None,
                           debug: bool = False,
                           output: Optional[str] = None):

        url_path = _CREATE_SIM_PACKAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            packagename=name
        )
        url = urljoin(self._api_url, url_path)

        data = { "startInstanceCount": start_instance_count, "coresPerInstance": cores_per_instance, "memInGbPerInstance": memory_in_gb_per_instance,
                 "displayName": display_name, "description": description, "osType": os_type, "packageType": package_type, "imagePath": image_path,
                 "minInstanceCount": min_instance_count, "maxInstanceCount": max_instance_count, "autoScale": auto_scale, "autoTerminate": auto_terminate}
        return self._put(url=url, data=data, debug=debug, output=output)

    def list_sim_package(self, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of simulator packages for {}...'.format(self._workspace_id))
        url_path = _LIST_SIM_PACKAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def get_sim_package(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about sim package {} in workspace {}...'.format(name, self._workspace_id))

        url_path = _GET_SIM_PACKAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename =name
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def update_sim_package(self, name: str,
                           start_instance_count: int,
                           cores_per_instance: float,
                           memory_in_gb_per_instance: float,
                           display_name: Optional[str] = None,
                           description: Optional[str] = None,
                           min_instance_count: int = 1,
                           max_instance_count: int = 1,
                           auto_scale: bool = False,
                           auto_terminate: bool = True,
                           workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Updating details for simulator package {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _UPDATE_SIM_PACKAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename = name
        )
        url = urljoin(self._api_url, url_path)

        data = {"startInstanceCount": start_instance_count, "coresPerInstance": cores_per_instance, "memInGbPerInstance": memory_in_gb_per_instance,
                "displayName": display_name, "description": description, "minInstanceCount": min_instance_count,
                "maxInstanceCount": max_instance_count, "autoScale": auto_scale,"autoTerminate": auto_terminate}
        return self._patch(url=url, data=data, debug=debug, output=output)

    def delete_sim_package(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Deleting simulator package {}'.format(name))
        url_path = _DELETE_SIM_PACKAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename = name
        )
        url = urljoin(self._api_url, url_path)
        return self._delete(url=url, debug=debug, output=output)

    def create_sim_collection(self,
                              packagename: str,
                              brain_name: str,
                              brain_version: int,
                              concept_name: str,
                              purpose_action: str,
                              description: Optional[str] = None,
                              cores_per_instance: Optional[str] = None,
                              memory_in_gb_per_instance: Optional[str] = None,
                              start_instance_count: Optional[str] = None,
                              min_instance_count: Optional[str] = None,
                              max_instance_count: Optional[str] = None,
                              auto_scaling: Optional[str] = None,
                              auto_termination: Optional[str] = None,
                              workspace: Optional[str] = None,
                              debug: bool = False,
                              output: Optional[str] = None):
        log.debug('Creating a new sim collection')
        url_path = _CREATE_SIM_COLLECTION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename=packagename
        )
        url = urljoin(self._api_url, url_path)

        purpose = json.loads(
            "{{\"action\": \"{}\", \"target\": {{\"workspaceName\": \"{}\", \"brainName\": \"{}\", \"brainVersion\": \"{}\", \"conceptName\": \"{}\"  }} }}".format(
                purpose_action, self._workspace_id, brain_name, brain_version, concept_name))

        data = {"purpose": purpose, "description": description,
                "resourceGroupName": '', "Subscription": '',
                "coresPerInstance": cores_per_instance, "memInGBPerInstance": memory_in_gb_per_instance,
                "startInstanceCount": start_instance_count, "minInstanceCount": min_instance_count,
                "maxInstanceCount": max_instance_count, "autoScaling": auto_scaling,
                "autoTermination": auto_termination}

        return self._post(url=url, data=data, debug=debug, output=output)

    def list_sim_collection(self, sim_package_name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of simulator collections of sim package {} in workspace...'.format(sim_package_name, self._workspace_id))
        url_path = _LIST_SIM_COLLECTION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename=sim_package_name
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def list_sim_base_images(self, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of simulator base images')
        url_path = _LIST_SIM_BASE_IMAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id
        )
        url = urljoin(self._api_url, url_path)
        return self._get(url=url, debug=debug, output=output)

    def get_sim_collection(self, sim_package_name: str, collection_id: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about sim collection {} of sim package {} in workspace {}...'.format(collection_id, sim_package_name, self._workspace_id))

        url_path = _GET_SIM_COLLECTION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename =sim_package_name,
            collectionid=collection_id
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def get_sim_base_image(self, image_identifier: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details for simulator base image {}...'.format(image_identifier))
        url_path = _GET_SIM_BASE_IMAGE_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            imageidentifier =image_identifier
        )
        url = urljoin(self._api_url, url_path)
        return self._get(url=url, debug=debug, output=output)

    def update_sim_collection(self,
                sim_package_name: str,
                collection_id: str,
                description: Optional[str] = None,
                workspace: Optional[str] = None,
                debug: bool = False,
                output: Optional[str] = None):
        log.debug('Updating details for sim collection {} of sim package {} in workspace {}...'.format(collection_id, sim_package_name, self._workspace_id))
        url_path = _UPDATE_SIM_COLLECTION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackageName = sim_package_name,
            collectionid=collection_id
        )
        url = urljoin(self._api_url, url_path)

        data = {"description": description}
        return self._patch(url=url, data=data, debug=debug, output=output)

    def delete_sim_collection(self, sim_package_name: str, collection_id: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Deleting for sim collection {} of sim package {} in workspace {}...'.format(collection_id, sim_package_name, self._workspace_id))
        url_path = _DELETE_SIM_COLLECTION_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            simulatorpackagename=sim_package_name,
            collectionid=collection_id
        )
        url = urljoin(self._api_url, url_path)
        return self._delete(url=url, debug=debug, output=output)

    def start_training(self, name: str, version: int = 1, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        url_path = _START_BRAIN_TRAINING_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )

        url = urljoin(self._api_url, url_path)

        return self._post(url=url, debug=debug, output=output)

    def stop_training(self, name: str, version: int = 1, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        url_path = _STOP_BRAIN_TRAINING_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )

        url = urljoin(self._api_url, url_path)

        return self._post(url=url, debug=debug, output=output)

    def reset_training(self, name: str, version: int, concept_name: str, lesson_number: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        url_path = _RESET_BRAIN_TRAINING_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )

        url = urljoin(self._api_url, url_path)

        concepts = [{"name":concept_name, "lessonIndex": lesson_number}]
        data = { "resetAll": False, "concepts": concepts}
        return self._post(url=url, data=data, debug=debug, output=output)

    def start_assessment(self, name: str, version: int = 1, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        url_path = _START_BRAIN_ASSESSMENT_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )

        url = urljoin(self._api_url, url_path)

        return self._post(url=url, debug=debug, output=output)

    def stop_assessment(self, name: str, version: int = 1, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        url_path = _STOP_BRAIN_ASSESSMENT_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            name=name,
            version=version
        )

        url = urljoin(self._api_url, url_path)

        return self._post(url=url, debug=debug, output=output)

    def create_exported_brain(self,
                              name: str,
                              processor_architecture: str,
                              brain_name: str,
                              brain_version: int,
                              display_name: Optional[str] = None,
                              description: Optional[str] = None,
                              workspace: Optional[str] = None,
                              debug: bool = False,
                              output: Optional[str] = None):
        log.debug('Creating a new exported brain {}'.format(name))
        url_path = _CREATE_EXPORTED_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
        )
        url = urljoin(self._api_url, url_path)

        data = {"name": name,
                "subscription": '', "resourceGroup": '',
                "processorArchitecture": processor_architecture, "brainName": brain_name,
                "brainVersion": brain_version, "displayName": display_name, "description": description}

        return self._post(url=url, data=data, debug=debug, output=output)

    def list_exported_brain(self, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of exported brains for {}...'.format(self._workspace_id))
        url_path = _LIST_EXPORTED_BRAINS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def get_exported_brain(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about exported brain {} in workspace {}...'.format(name, self._workspace_id))

        url_path = _GET_EXPORTED_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            exportedbrainname =name
        )
        url = urljoin(self._api_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def update_exported_brain(self, name: str, display_name: Optional[str] = None, description: Optional[str] = None, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Updating details for exported brain {} in workspace {}...'.format(name, self._workspace_id))
        url_path = _UPDATE_EXPORTED_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            exportedbrainname = name
        )
        url = urljoin(self._api_url, url_path)

        data = {"displayName": display_name, "description": description}
        return self._put(url=url, data=data, debug=debug, output=output)

    def delete_exported_brain(self, name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Deleting exported brain {}'.format(name))
        url_path = _DELETE_EXPORTED_BRAIN_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            exportedbrainname = name
        )
        url = urljoin(self._api_url, url_path)
        return self._delete(url=url, debug=debug, output=output)

    def list_unmanaged_sim_session(self, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting list of simulator sessions for {}...'.format(self._workspace_id))
        url_path = _LIST_SIM_SESSIONS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id
        )

        url = urljoin(self._gateway_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def get_sim_session(self, session_id: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Getting details about simulator session {} in workspace {}...'.format(session_id, self._workspace_id))

        url_path = _GET_SIM_SESSIONS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            sessionid=session_id
        )

        url = urljoin(self._gateway_url, url_path)

        return self._get(url=url, debug=debug, output=output)

    def patch_sim_session(self, session_id: str, brain_name: str, version: int, purpose_action: str, concept_name: str, workspace: Optional[str] = None, debug: bool = False, output: Optional[str] = None):
        log.debug('Patching details about simulator session {} in workspace {}...'.format(session_id, self._workspace_id))

        url_path = _PATCH_SIM_SESSIONS_URL_PATH_TEMPLATE.format(
            workspacename=workspace if workspace else self._workspace_id,
            sessionid=session_id
        )

        url = urljoin(self._gateway_url, url_path)

        purpose = json.loads(
            "{{\"action\": \"{}\", \"target\": {{\"workspaceName\": \"{}\", \"brainName\": \"{}\", \"brainVersion\": \"{}\", \"conceptName\": \"{}\"  }} }}".format(
                purpose_action, self._workspace_id, brain_name, version, concept_name))

        data = {"purposeOperation": 'SetValue', "purpose": purpose}

        return self._patch(url=url, data=data, debug=debug, output=output)

    def _raise_on_redirect(self, response: requests.Response):
        """ Raises an HTTPError if the response is 301.

        Substitute a helpful error message for the often confusing errors
        produced by default redirect logic.

        :param response: requests.Response object to be processed
        """
        if (response.status_code == 301):
            raise requests.exceptions.HTTPError(
                "{} Moved Permanently: Likely misconfigured url: {}".format(
                    response.status_code, self._api_url)
            )