import uuid
from pprint import pprint
import radical.pilot as rp
import os
from exceptions import *
import traceback

def resolve_pathholders(path, shared_path):

    if '///' not in path:
        return os.path.expandvars(path)

    schema, relative_path = path.split(':///')

    if schema == 'staging':
        resolved_path = 'pilot:///' + os.path.basename(relative_path)

    elif schema == 'sandbox':
        resolved_path = path.replace(schema + '://', shared_path + '/')

    elif schema == 'file':
        resolved_path = path.replace(schema + '://', relative_path)

    return os.path.expandvars(resolved_path)


def get_input_staging(task_details, shared_path):

    staging_directives = []

    for entity in task_details:

        if not isinstance(entity, dict):
            break

        staging_type = entity['_cls']

        if staging_type in ['Link', 'Copy']:

            src = resolve_pathholders(
                entity['_dict']['source']['_dict']['location'], shared_path)
            dest = os.path.basename(
                resolve_pathholders(entity['_dict']['target']['_dict']['location'], shared_path))

            if staging_type == 'Link':
                rp_staging_type = rp.LINK

            elif staging_type == 'Copy':
                rp_staging_type = rp.COPY

        temp_directive = {
            'source': src,
            'action': rp_staging_type,
            'target': 'unit:///' + dest
        }

        if temp_directive not in staging_directives:
            staging_directives.append(temp_directive)


    print staging_directives

    return staging_directives


def get_executable_arguments(task_details):

    raw_exec = None
    proc_exec = None

    for entity in task_details:
        if not isinstance(entity, dict):
            raw_exec = [str(entity)]
            break

    #print raw_exec[0]

    proc_exec = raw_exec[0][107:]
    proc_exec = proc_exec[:-31]

    #print raw_exec[0]
    if ';' in raw_exec[0]:
        # for the regular trajectory tasks
        proc_exec = raw_exec[0].split(';')[2].replace('then','').replace('worker://','').replace('=', ' ').replace('"','').strip()
    else:
        # for the modeler task
        proc_exec = raw_exec[0].strip()
    #print proc_exec

    exe = proc_exec.split(' ')[0]
    args = proc_exec.split(' ')[1:]

    #print exe, args

    return exe, args


def add_output_staging(task_desc, db, shared_path):

    hex_id_input = hex_to_id(hex_uuid=task_desc['_dict']['generator']['_hex_uuid'])

    src_files = db.get_source_files(hex_id_input)

    hex_id_output = hex_to_id(hex_uuid=task_desc['_dict']['_main'][-1]['_dict']['target']['_hex_uuid'])
    output_loc = db.get_file_destination(hex_id_output)

    staging_directives = list()

    for file in src_files:

        temp = {
                    'source': os.path.basename(os.path.abspath(task_desc['_dict']['_main'][-1]['_dict']['source']['_dict']['location'])) + '/' + file,
                    'action': rp.COPY,
                    'target': resolve_pathholders(output_loc, shared_path) + '/' + file
                }

        staging_directives.append(temp)

    #print staging_directives

    return staging_directives


def create_cud_from_task_def(task_descs, db, shared_path):


    try:
        cuds = list()

        for task_desc in task_descs:

            task_details = task_desc['_dict']['_main']

            cud = rp.ComputeUnitDescription()
            cud.name = task_desc['_id']
            cud.pre_exec = ['export PATH=/home/vivek/Research/tools/miniconda2/bin:$PATH','mkdir -p traj']
            exe, args = get_executable_arguments(task_details)
            cud.executable = [str(exe)]
            cud.arguments = args
            cud.input_staging = get_input_staging(task_details, shared_path)
            cud.output_staging = add_output_staging(task_desc, db, shared_path)
            cud.cores = 1  # currently overwriting

            db.update_task_description_status(task_desc['_id'], 'done')

            #print cud.executable, cud.arguments

            cuds.append(cud)
        
        return cuds

    except Exception as ex:

        print traceback.format_exc()
        raise Error(msg=ex)


def process_resource_requirements(raw_res_descs):

    resources = list()
    for res_desc in raw_res_descs:

        temp_desc = dict()
        temp_desc['total_cpus'] = res_desc['_dict']['total_cpus']
        temp_desc['total_gpus'] = res_desc['_dict']['total_gpus']
        temp_desc['total_time'] = res_desc['_dict']['total_time']
        temp_desc['resource']   = res_desc['_dict']['destination']
        resources.append(temp_desc)

    return resources


def process_configurations(conf_descs):

    configurations = list()
    for conf in conf_descs:

        if not conf['_dict']['queues']:

            temp_desc = dict()
            temp_desc['resource']       = conf['_dict']['resource_name']
            temp_desc['project']        = conf['_dict']['allocation']
            temp_desc['shared_path']    = conf['_dict']['shared_path']
            temp_desc['queue']          = ''

            configurations.append(temp_desc)

        else:

            for queue in conf['_dict']['queues']:

                temp_desc = dict()
                temp_desc['resource']       = conf['_dict']['resource_name']
                temp_desc['project']        = conf['_dict']['allocation']
                temp_desc['shared_path']    = conf['_dict']['shared_path']
                temp_desc['queue']          = queue

                configurations.append(temp_desc)

    return configurations


def generic_matcher(the_list=None, key='', value=''):
    """Searches a list and matches all of the ones entries which 'key'
    and 'value' match. The values should be inside of the '_dict' object.
    :Parameters:
    - `the_list`: list to search through
    - `key`: key of the item to match
    - `value`: value of the item to match
    """

    if not value:
        return the_list

    matching = list()
    if the_list:
        for item in the_list:
            matching_value = item[key]
            if matching_value.lower() in [value.lower()]:
                matching.append(item)
    return matching


def get_matching_configurations(configurations=None, resource_name=''):
    """Searches for a configuration descriptions list and matches all of the ones
    that match the specific resource_name.
    :Parameters:
    - `configurations`: list of configurations descriptions to search through
    - `resource_name`: resource name to match
    """
    return generic_matcher(
        the_list=configurations,
        key='resource',
        value=resource_name
    )


def hex_to_id(hex_uuid=None):
    """Convert a hexadecimal string to an ID"""
    the_id = None
    if hex_uuid:
        if hex_uuid.endswith('L'):
            hex_uuid = hex_uuid[:-1]
        temp = uuid.UUID(int=int(hex_uuid, 16))
        the_id = str(temp)
    return the_id
