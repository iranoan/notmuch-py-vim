" Vim syntax file
" Language: notmuch-show window

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

" Syntax clusters
syntax cluster mailHeaderFields contains=mailHeaderKey,mailHeaderEmail,@mailLinks
syntax cluster mailLinks        contains=mailURL,mailEmail
syntax cluster mailQuoteExps    contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

syntax case match
syntax case ignore

syntax region  mailNewPart      contains=mailNewPartHead,mailHeader,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold

" Usenet headers
syntax match   mailHeaderKey    contained contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/
syntax match   mailNewPartHead  contains=@NoSpell '^[\x0C]\zs.\+ part$'
syntax region  mailHeader       contains=mailHideHeader,@mailHeaderFields,@NoSpell start='^[a-z-]\+:.\+[\u200B]' skip='^\s' end='^[^:]*\n' fold

execute 'source ' . expand('<sfile>:p:h:h') . '/macros/syntax-common.vim'

highlight mailNewPartHead term=reverse,bold gui=reverse,bold

let b:current_syntax = 'notmuch-show'

let &cpoptions = s:cpo_save
unlet s:cpo_save
