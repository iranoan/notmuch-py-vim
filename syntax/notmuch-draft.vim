" Vim syntax file
" Language: notmuch-draft window

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

syntax case match
syntax case ignore

syntax match   mailMultiHead   contained contains=@NoSpell '^--\(\([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$'
syntax region  mailMultiHeader contained contains=mailHeaderKey,mailMultiHead,@mailHeaderFields,@NoSpell start='^--\(\([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$' skip='^\s' end='^$' fold
syntax region  mailMultiPart   keepend       contains=mailMultiHeader,@mailHeaderFields,@NoSpell start='^--\z\(\([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$' end='^--\z1--$' end='^--\z1$'me=s-1  fold

syntax match mailHeaderKey      contained contains=mailHeaderEmail,mailEmail,@NoSpell /^[a-z-]\+:\s*/
syntax region mailHeaderAddress contained contains=mailHeaderKey,mailHeaderEmail,mailEmail,@NoSpell start='^\(\(Resent-\)\?\(From\|To\|Cc\|Bcc\)\|Reply-To\):\s*' skip='^\s' end='$'
syntax match mailHeaderFcc      contained contains=mailHeaderKey,@NoSpell /^Fcc:\s*.\+/
" syntax region mailHeader2        keepend   contains=mailHideHeader, @mailHeaderFields2,@mailQuoteExps,@NoSpell start='^\(\(Resent-\)\?From\|Date\|From\|Received\|Return-Path\):' skip='^\s' end='^$'me=s-1 fold
syntax region mailHeader2                 contains=mailHeaderKey,mailHideHeader,mailHeaderAddress,mailHeaderFcc,@mailHeaderFields,@NoSpell start='\%^' skip='^\s' end='^$'me=s-1 fold

execute 'source ' . expand('<sfile>:p:h:h') . '/macros/syntax-common.vim'

highlight def link mailHeaderAddress Statement
highlight def link mailHeaderFcc     Statement
highlight def link mailMultiHeader   Statement
highlight def link mailHeader2       mailHeader
highlight def link mailMultiHead mailNewPartHead

let b:current_syntax = 'notmuch-draft'

let &cpoptions = s:cpo_save
unlet s:cpo_save
