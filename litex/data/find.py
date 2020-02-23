def find_data(data_type, data_name):
    imp = "from litex.data.{} import {} as dm".format(data_type, data_name)
    try:
        exec(imp)
        return dm.data_location
    except ImportError as e:
        raise ImportError("""\
litex-data-{dt}-{dn} module not install! Unable to use {dn} {dt}.
{e}

You can install this by running;
 pip install git+https://github.com/litex-hub/litex-data-{dt}-{dn}.git
""".format(dt=data_type, dn=data_name, e=e))
