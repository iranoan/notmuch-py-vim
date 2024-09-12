" Author:  Iranoan <iranoan+vim@gmail.com>
" License: GPL Ver.3.

scriptencoding utf-8

if exists('g:loaded_notmuch_py')
	finish
endif
let g:loaded_notmuch_py = 1

let s:save_cpo = &cpoptions
set cpoptions&vim

if !has('python3') || v:version < 900 || !has('vim9script')
	echohl ErrorMsg | echomsg 'Require +python3 and Ver.9.00, Vim9 script.' | echohl None
	let &cpoptions = s:save_cpo
	unlet s:save_cpo
	finish
endif

if has('nvim')
	echohl ErrorMsg | echomsg 'The plugin don''t work with NeoVim.' | echohl None
	let &cpoptions = s:save_cpo
	unlet s:save_cpo
	finish
endif

let g:notmuch_command = { 'start': ['s:start_notmuch', 0x0c], 'mail-new': ['s:new_mail', 0x11] }

if !exists(':Notmuch')
	command -range -nargs=* -complete=customlist,notmuch_py#Comp_all_args Notmuch call notmuch_py#Notmuch_main(<line1>, <line2>, <q-args>)
else
	echohl ErrorMsg | echomsg 'Already define Notmuch command.' | echohl None
endif

" Reset User condition
let &cpoptions = s:save_cpo
unlet s:save_cpo
