/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <json-c/json.h>
#include "error.h"
#include "modules.h"

static int file_to_js(char *filename, json_object **obj)
{
  int ret = RC_OK;
  struct json_tokener *tok=NULL;
  json_object *pobj=NULL;
  enum json_tokener_error jerr;
  FILE *in=NULL;
  int linenum=0;
  char *lineptr=NULL;
  size_t len, len2;

  if(!filename || !obj)
  {
    ret=RC_INVARG;
    goto out;
  }

  in = fopen(filename, "r");
  if(!in)
  {
    eprintf("Can't open configuration file: %s\n", filename);
    ret= RC_ERROR;
    goto out;
  }

  tok = json_tokener_new();
  if(!tok)
  {
    ret=RC_ERROR;
    eprintf("Can't create new tokener\n");
    goto out;
  }

  do
  {
    linenum++;
    len=32768;
    len2 = getline(&lineptr, &len, in);
    if(len2 == -1)
    {
      ret=RC_ERROR;
      eprintf("End of file !\n");
      goto out;
    }
    pobj = json_tokener_parse_ex(tok, lineptr, len2);
    if((jerr = json_tokener_get_error(tok)) == json_tokener_success)
    {
      break;
    }

    if((jerr = json_tokener_get_error(tok)) != json_tokener_continue)
    {
      fprintf(stderr, "ERROR in %s:\n", filename);
      fprintf(stderr, "line:%d:\n%s",linenum, lineptr);
      jerr = json_tokener_get_error(tok);
      fprintf(stderr, "json parse error: %s\n", json_tokener_error_desc(jerr));
      goto out;
    }
    free(lineptr);
    lineptr=NULL;
  }while(1);

  *obj=pobj;
  pobj=NULL;
out:

  if(pobj)
  {
    json_object_put(pobj);
  }
  if(tok)
  {
    json_tokener_free(tok);
  }
  if(lineptr)
  {
    free(lineptr);
  }
  if(in)
  {
    fclose(in);
  }
  return ret;
}

static int json_to_interface_list(json_object *interface, struct interface_s **iface)
{
  int ret=RC_OK;
  int n, i;
  json_object *obj;
  json_object *name;
  json_object *index;

  struct interface_s *t_iface=NULL;

  if(!interface || !iface)
  {
    ret = RC_INVARG;
    eprintf("Invalid argument\n");
    goto out;
  }

  if(!json_object_is_type(interface, json_type_array))
  {
    ret=RC_JSERROR;
    eprintf("Interface must be an array\n");
    goto out;
  }

  n = json_object_array_length(interface);
  t_iface = (struct interface_s *)malloc(sizeof(struct interface_s) * (n + 1));
  if(!t_iface)
  {
    ret=  RC_NOENMEM;
    eprintf("Not enough memory\n");
    goto out;
  }
  memset(t_iface, 0,sizeof(struct interface_s) * (n + 1));

  for(i = 0; i < n; i++)
  {
    obj = json_object_array_get_idx(interface, i);
    if(json_object_is_type(obj, json_type_object))
    {
      if(!json_object_object_get_ex(obj, "name", &name))
      {
	ret=RC_JSERROR;
	eprintf("Module interface must have a name (%s)!\n", json_object_to_json_string(obj));
	goto out;
      }
      t_iface[i].name = strdup(json_object_get_string(name));

      if(json_object_object_get_ex(obj, "index", &index))
      {
	if(!json_object_is_type(index, json_type_int))
	{
	  ret = RC_JSERROR;
	  eprintf("Interface Index must be an int ! (%s)\n", json_object_to_json_string(obj));
	}
	t_iface[i].index = json_object_get_int(index);
      }
    }
    if(json_object_is_type(obj, json_type_string))
    {
      t_iface[i].name = strdup(json_object_get_string(obj));
    }
  }
  *iface = t_iface;
  t_iface = NULL;
out:
  if(t_iface)
  {
    free(t_iface);
  }
  return ret;
}

static int module_list_free(struct module_s *mod)
{
  int ret=RC_OK;
  struct module_s *mnext;
  int i;
  while(mod)
  {
    mnext = mod->next;
    if(mod->iface)
    {
      for(i = 0; i < mod->niface; i++)
      {
	if(mod->iface[i].name)
	{
	  free(mod->iface[i].name);
	}
      }
      free(mod->iface);
      if(mod->name)
      {
	free(mod->name);
      }
      if(mod->args)
      {
	free(mod->args);
      }
    }
    free(mod);
    mod = mnext;
  }
  return ret;
}

static int json_to_module_list(json_object *obj, struct module_s **mod)
{
  struct module_s *m=NULL;
  struct module_s *first=NULL;

  json_object *tobj;
  int ret=RC_OK;
  int i, n, len;
  json_object *name;
  json_object *args;
  json_object *interface;
  json_object *tickfirst;

  if(!obj || !mod)
  {
    ret = RC_INVARG;
    eprintf("Wrong arguments\n");
    goto out;
  }

  if(!json_object_is_type(obj, json_type_array))
  {
    ret=RC_JSERROR;
    eprintf("Config file must be an array\n");
    goto out;
  }

  n = json_object_array_length(obj);
  for(i = 0; i < n; i++)
  {
    tobj = json_object_array_get_idx(obj, i);

    if(!json_object_object_get_ex(tobj, "module", &name))
    {
      continue;
    }

    if(!json_object_object_get_ex(tobj, "interface", &interface))
    {
      ret=RC_JSERROR;
      eprintf("expected \"interface\" in object (%s)\n", json_object_to_json_string(tobj));
      goto out;
    }

    args = NULL;
    json_object_object_get_ex(tobj, "args", &args);

    tickfirst=NULL;
    json_object_object_get_ex(tobj, "tickfirst", &tickfirst);


    if(m)
    {
      m->next=(struct module_s *)malloc(sizeof(struct module_s));
      m=m->next;
    }
    else
    {
      m=(struct module_s *)malloc(sizeof(struct module_s));
    }
    if(!m)
    {
      ret = RC_NOENMEM;
      eprintf("Not enough memory\n");
      goto out;
    }
    if(!first)
    {
      first = m;
    }
    memset(m, 0, sizeof(struct module_s));
    ret = json_to_interface_list(interface, &m->iface);
    if(RC_OK != ret)
    {
      goto out;
    }
    len = 0;

    while(m->iface[len++].name);
    m->niface= len-1;
    m->name = strdup(json_object_get_string(name));
    if(args)
    {
      m->args = strdup(json_object_to_json_string(args));
    }
    if(tickfirst)
    {
      m->tickfirst = json_object_get_boolean(tickfirst);
    }
  }

  if (!m)
  {
      ret = RC_JSERROR;
      eprintf("No modules found in config file:\n%s\n", json_object_to_json_string(obj));
      goto out;
  }

  *mod = first;
  first=NULL;

out:
  if(first)
  {
    module_list_free(first);
  }
  return ret;
}

static int json_get_timebase(json_object *obj, uint64_t *timebase)
{
  json_object *tobj;
  int ret=RC_OK;
  int i, n;
  uint64_t _timebase = 0;
  json_object *json_timebase;

  if(!obj || !timebase)
  {
    ret = RC_INVARG;
    eprintf("Wrong arguments\n");
    goto out;
  }

  if(!json_object_is_type(obj, json_type_array))
  {
    ret=RC_JSERROR;
    eprintf("Config file must be an array\n");
    goto out;
  }

  n = json_object_array_length(obj);
  for(i = 0; i < n; i++)
  {
    tobj = json_object_array_get_idx(obj, i);

    if(!json_object_object_get_ex(tobj, "timebase", &json_timebase))
    {
      continue;
    }

    if (_timebase != 0)
    {
      ret=RC_JSERROR;
      eprintf("\"timebase\" found multiple times: in object (%s)\n", json_object_to_json_string(tobj));
      goto out;
    }

    _timebase = json_object_get_int64(json_timebase);
    if (_timebase == 0)
    {
      ret=RC_JSERROR;
      eprintf("\"timebase\" cannot be zero: in object (%s)\n", json_object_to_json_string(tobj));
      goto out;
    }
  }

  if (_timebase == 0)
  {
    ret=RC_JSERROR;
    eprintf("No \"timebase\" found in config:\n%s\n", json_object_to_json_string(obj));
    goto out;
  }
  *timebase = _timebase;

out:
  return ret;
}


int litex_sim_file_parse(char *filename, struct module_s **mod, uint64_t *timebase)
{
  struct module_s *m=NULL;
  json_object *obj=NULL;
  int ret=RC_OK;

  if(!filename || !mod)
  {
    ret = RC_INVARG;
    eprintf("Invalid argument\n");
    goto out;
  }

  ret = file_to_js(filename, &obj);
  if(RC_OK != ret)
  {
    goto out;
  }

  ret = json_get_timebase(obj, timebase);
  if(RC_OK != ret)
  {
    goto out;
  }

  ret = json_to_module_list(obj, &m);
  if(RC_OK != ret)
  {
    goto out;
  }

  *mod = m;
  m = NULL;
out:
  if(m)
  {
    module_list_free(m);
  }
  if(obj)
  {
    json_object_put(obj);
  }
  return ret;
}
