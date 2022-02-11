" Vim syntax file
" Language: notmuch-show window

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

syntax case match
syntax case ignore

syntax match   mailNewPartHead  contained contains=@NoSpell '^[\x0C]\zs.\+ part$'
syntax region  mailHeader      contained contains=mailHeaderKey,mailNewPartHead,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' skip='^\s' end='^[^:]*\n' fold
syntax region  mailNewPart      contains=mailHeader,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold

" Usenet headers
syntax match   mailHeaderKey    contained contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/
" syntax region  mailHeader       contains=@mailHeaderFields,@NoSpell start='^[a-z-]\+:.\+[\u200B]' skip='^\s' end='^[^:]*\n' fold
syntax region mailHeader                 contains=mailHeaderKey,mailHideHeader,@mailHeaderFields,@NoSpell start='\%^' skip='^\s' end='^$'me=s-1 fold

execute 'source ' . expand('<sfile>:p:h:h') . '/macros/syntax-common.vim'

let b:current_syntax = 'notmuch-show'

let &cpoptions = s:cpo_save
unlet s:cpo_save
