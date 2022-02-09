" Vim syntax file
" Language: notmuch-draft window

" Quit when a syntax file was already loaded
" if exists('b:current_syntax')
" 	finish
" endif

let s:cpo_save = &cpoptions
set cpoptions&vim

" Syntax clusters
syntax cluster mailHeaderFields contains=mailHeaderKey,mailHeaderEmail,mailHeaderAddress,mailHeaderFcc,@mailLinks
syntax cluster mailHeaderFields2 contains=mailHeaderKey,mailHeaderEmail,mailHeaderAddress,mailHeaderFcc,@mailLinks
syntax cluster mailLinks        contains=mailURL,mailEmail
syntax cluster mailQuoteExps    contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

syntax case match
syntax case ignore

syntax match mailHeaderKey      contained contains=mailHeaderEmail,mailEmail,@NoSpell /^[a-z-]\+:\s*/
syntax region mailHeaderAddress contained contains=@mailHeaderFields2,mailHeaderEmail,mailEmail,@NoSpell start='^\(\(Resent-\)\?\(From\|To\|Cc\|Bcc\)\|Reply-To\):\s*'ms=s,me=e skip='^\s' end='$'
syntax match mailHeaderFcc      contained contains=@mailHeaderFields2,@NoSpell /^Fcc:\s*.\+/
syntax region mailHeader        keepend   contains=mailHideHeader, @mailHeaderFields,@mailQuoteExps,@NoSpell start='^\(\(Resent-\)\?From\|Date\|From\|Received\|Return-Path\):' skip='^\s' end='^$'me=s-1 fold

execute 'source ' . expand('<sfile>:p:h:h') . '/macros/syntax-common.vim'
highlight def link mailHeaderAddress Statement
highlight def link mailHeaderFcc     Statement

let b:current_syntax = 'notmuch-draft'

let &cpoptions = s:cpo_save
unlet s:cpo_save
