" Vim syntax file
" Language: notmuch-show window

" Quit when a syntax file was already loaded
if exists('b:current_syntax')
	finish
endif

let s:cpo_save = &cpoptions
set cpoptions&vim

" Syntax clusters
syntax cluster mailHeaderFields	contains=mailHeaderKey,mailHeaderEmail,@mailLinks
syntax cluster mailLinks		contains=mailURL,mailEmail
syntax cluster mailQuoteExps	contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

syntax case match
syntax case ignore

syntax region	mailNewPart	contains=mailNewPartHead,mailHeader,@mailHeaderFields,@NoSpell start='^[\x0C].\+ part$' end='^[\x0C]'me=e-1 fold

" Usenet headers
syntax match	mailHeaderKey	contained contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/
syntax match	mailNewPartHead	contains=@NoSpell '^[\x0C]\zs.\+ part$'
syntax region	mailHeader	contains=mailHideHeader,@mailHeaderFields,@NoSpell start='^[a-z-]\+:.\+\t$' skip='^\s' end='^[^:]*\n' fold
execute 'syntax region	mailHideHeader	contains=@mailHeaderFields,@NoSpell '
			\ . 'start=''' . '^\(' . join(g:notmuch_show_hide_headers, '\|')[:-2] . '\):' . '''me=s-1 '
			\ . 'end=''\(\(Del-\)\?\(Attach\|HTML\)\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\):''me=s-1 '
			\ . 'end=''^[^:]*\n''me=s-1  fold'
" syntax region	mailHideHeader	contains=@mailHeaderFields,@NoSpell start='^\(Return-Path\|Reply-To\|Message-ID\|Resent-Message-ID\|In-Reply-To\|References\|Errors-To\):' end='\(\(Del-\)\?\(Attach\|HTML\)\|\(Not-\)\?Decrypted\|Encrypt\|PGP-Public-Key\|\(Good-\|Bad-\)\?Signature\)'me=s-1 end='^[^:]*\n'me=s-1 fold

" Anything in the header between < and > is an email address
syntax match	mailHeaderEmail	contained contains=@NoSpell '<.\{-}>'

" Mail Signatures. (Begin with "-- ", end with change in quote level)
syntax region	mailSignature	keepend contains=@mailLinks,@mailQuoteExps start='^--\s$' end='^\n' end='^\(> \?\)\+' fold
syntax region	mailSignature	keepend contains=@mailLinks,@mailQuoteExps,@NoSpell start='^\z(\(> \?\)\+\)--\s$' end='^\z1$' end='^\z1\@!' end='^\z1\(> \?\)\+' fold

" Treat verbatim Text special.
syntax region	mailVerbatim	contains=@NoSpell keepend start='^#v+$' end='^#v-$' fold
syntax region	mailVerbatim	contains=@mailQuoteExps,@NoSpell keepend start='^\z(\(> \?\)\+\)#v+$' end='\z1#v-$' fold

" URLs start with a known protocol or www,web,w3.
syntax match mailURL contains=@NoSpell `\v<(((https?|ftp|gopher)://|(mailto|file|news):)[^' \t<>"]+|(www|web|w3)[a-z0-9_-]*\.[a-z0-9._-]+\.[^' \t<>"]+)[a-z0-9/]`
syntax match mailEmail contains=@NoSpell '\v[_=a-z\./+0-9-]+\@[a-z0-9._-]+\a{2}'

" Make sure quote markers in regions (header / signature) have correct color
syntax match mailQuoteExp1	contained '\v^(\> ?)'
syntax match mailQuoteExp2	contained '\v^(\> ?){2}'
syntax match mailQuoteExp3	contained '\v^(\> ?){3}'
syntax match mailQuoteExp4	contained '\v^(\> ?){4}'
syntax match mailQuoteExp5	contained '\v^(\> ?){5}'
syntax match mailQuoteExp6	contained '\v^(\> ?){6}'

" Even and odd quoted lines. Order is important here!
syntax region	mailQuoted6	keepend contains=mailVerbatim,mailHemailHideHeaderader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{5}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted5	keepend contains=mailQuoted6,mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{4}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted4	keepend contains=mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{3}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted3	keepend contains=mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{2}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted2	keepend contains=mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{1}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted1	keepend contains=mailQuoted2,mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z([a-z]\+>\|[]}>]\)' end='^\z1\@!' fold

" Need to sync on the header. Assume we can do that within 100 lines
if exists('mail_minlines')
	execute 'syn sync minlines=' . mail_minlines
else
	syntax sync minlines=100
endif

" Define the default highlighting.
highlight def link mailVerbatim	Special
highlight def link mailHeader		Statement
highlight def link mailHeaderKey	Type
highlight def link mailSignature	PreProc
highlight def link mailHeaderEmail	mailEmail
highlight def link mailEmail		Special
highlight def link mailURL		String
" highlight def link mailSubject		Title
highlight					 mailNewPartHead	term=reverse,bold gui=reverse,bold
highlight def link mailQuoted1		Comment
highlight def link mailQuoted3		mailQuoted1
highlight def link mailQuoted5		mailQuoted1
highlight def link mailQuoted2		Identifier
highlight def link mailQuoted4		mailQuoted2
highlight def link mailQuoted6		mailQuoted2
highlight def link mailQuoteExp1	mailQuoted1
highlight def link mailQuoteExp2	mailQuoted2
highlight def link mailQuoteExp3	mailQuoted3
highlight def link mailQuoteExp4	mailQuoted4
highlight def link mailQuoteExp5	mailQuoted5
highlight def link mailQuoteExp6	mailQuoted6

let b:current_syntax = "notmuch-mail"

let &cpoptions = s:cpo_save
unlet s:cpo_save
