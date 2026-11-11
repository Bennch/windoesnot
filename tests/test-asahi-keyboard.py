#!/usr/bin/env python3
"""Verify real XKB symbols for both Mac @ choices and Option keys."""
import ctypes as c,sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'desktop/config/hypr/lua/bin'))
from hypr_state import configure_mac_keyboard
lib=c.CDLL('libxkbcommon.so.0')
class Names(c.Structure):_fields_=[(k,c.c_char_p) for k in ['rules','model','layout','variant','options']]
for name,args,result in [('xkb_context_new',[c.c_int],c.c_void_p),('xkb_keymap_new_from_names',[c.c_void_p,c.POINTER(Names),c.c_int],c.c_void_p),('xkb_state_new',[c.c_void_p],c.c_void_p),('xkb_keymap_key_by_name',[c.c_void_p,c.c_char_p],c.c_uint),('xkb_state_update_key',[c.c_void_p,c.c_uint,c.c_int],c.c_int),('xkb_state_key_get_utf8',[c.c_void_p,c.c_uint,c.c_char_p,c.c_size_t],c.c_int),('xkb_state_unref',[c.c_void_p],None),('xkb_keymap_unref',[c.c_void_p],None),('xkb_context_unref',[c.c_void_p],None)]:
 f=getattr(lib,name);f.argtypes=args;f.restype=result
for pref,key in [('l','AC09'),('q','AD01')]:
 opts={'input.kb_options':'compose:menu,lv3:ralt_switch'}
 configure_mac_keyboard(opts,'de',pref)
 assert 'compose:menu' in opts['input.kb_options']
 ctx=lib.xkb_context_new(0);names=Names(None,b'pc105',b'de',opts['input.kb_variant'].encode(),opts['input.kb_options'].encode());km=lib.xkb_keymap_new_from_names(ctx,c.byref(names),0);assert km
 for alt in ['LALT','RALT']:
  state=lib.xkb_state_new(km);lib.xkb_state_update_key(state,lib.xkb_keymap_key_by_name(km,alt.encode()),1)
  text=c.create_string_buffer(16);lib.xkb_state_key_get_utf8(state,lib.xkb_keymap_key_by_name(km,key.encode()),text,16)
  assert text.value==b'@',(pref,alt,text.value)
  lib.xkb_state_unref(state)
 lib.xkb_keymap_unref(km);lib.xkb_context_unref(ctx)
 print('PASS: both Option keys +',pref.upper(),'produce @; unrelated XKB options preserved')
 configure_mac_keyboard(opts,'us',pref)
 assert opts['input.kb_variant']=='' and opts['input.kb_options']=='compose:menu'
try:configure_mac_keyboard({},'de','not-valid')
except ValueError:pass
else:raise AssertionError('invalid preference accepted')
print('PASS: leaving German layout removes Mac mapping; invalid preference rejected')
