" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('g:loaded_notmuch_py')
	finish
endif
let g:loaded_notmuch_py = 1

let s:save_cpo = &cpoptions
set cpoptions&vim

if !has('python3') || v:version < 800 || !has('vimscript-4')
scriptversion 4
	echohl ErrorMsg | echomsg 'Require +python3 and Ver.8.00, vim script ver.4 or later.' | echohl None
	finish
endif

if has('nvim')
	echohl ErrorMsg | echomsg 'The plugin don''t work with NeoVim.' | echohl None
	finish
endif

let g:notmuch_command = { 'start': ['s:start_notmuch', 0x0c], 'mail-new': ['s:new_mail', 0x11] }

if !exists(':Notmuch')
	command -range -nargs=* -complete=customlist,notmuch_py#Comp_all_args Notmuch call notmuch_py#Notmuch_main(<line1>, <line2>, <f-args>)
else
	echohl ErrorMsg | echomsg 'Already define Notmuch command.' | echohl None
endif

" Reset User condition
let &cpoptions = s:save_cpo
unlet s:save_cpo
