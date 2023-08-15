" Vim syntax file
" Language: notmuch-draft window
scriptversion 4

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

syntax case ignore

execute 'source ' .. expand('<sfile>:p:h:h') .. '/macros/syntax-common.vim'

" Syntax clusters
syntax cluster	mailHeaderComp	contains=mailHeaderAddress,mailHeaderAttach,mailHeaderEncrypt,mailHeaderFcc,mailHeaderSignature

" Multipart
syntax match	mailMultiHead	contained	contains=@NoSpell '^--\%(\%([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$'
syntax region	mailMultiHeader	contained	contains=mailHeaderKey,mailMultiHead,@mailHeaderField,@NoSpell start='^--\%(\%([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$' skip='^\s' end='^$' fold
syntax region	mailMultiPart     keepend	contains=mailMultiHeader,@mailLinks,@NoSpell start='^--\z\(\%([a-z0-9-\.=_]\+[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9\._]\+[a-z0-9-\.=_]\+\|[a-z0-9-\.=_]\+[a-z0-9\._]\+\)[^-][^-]\)$' end='^--\z1--$' end='^--\z1$'me=s-1 fold

syntax region	mailHeaderAddress	contained	contains=mailHeaderKey,mailHeaderEmail,mailEmail,@NoSpell start='^\%(\%(Resent-\)\?\%(From\|To\|Cc\|Bcc\)\|Reply-To\):\s*' skip='^\s' end='$'
syntax region	mailHeaderAttach	contained	contains=mailHeaderKey,@NoSpell start='^Attach:\s*.\+' end='$'
syntax region	mailHeaderEncrypt	contained	contains=mailHeaderKey,@NoSpell start='^Encrypt:\s*.\+' end='$'
syntax region	mailHeaderFcc	contained	contains=mailHeaderKey,@NoSpell start='^Fcc:\s*.\+' end='$'
syntax region	mailHeaderSignature	contained	contains=mailHeaderKey,@NoSpell start='^Signature:\s*.\+' end='$'

highlight def link mailHeaderAddress	mailHeader
highlight def link mailHeaderAttach	mailHeader
highlight def link mailHeaderEncrypt	mailHeader
highlight def link mailHeaderFcc	mailHeader
highlight def link mailHeaderSignature mailHeader
highlight def link mailMultiHeader	mailHeader
highlight def link mailHeader2	mailHeader
highlight def link mailMultiHead	mailNewPartHead

let b:current_syntax = 'notmuch-draft'

let &cpoptions = s:cpo_save
unlet s:cpo_save
