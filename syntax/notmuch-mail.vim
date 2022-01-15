" Vim syntax file
" Language:		Mail file

" Quit when a syntax file was already loaded
if exists("b:current_syntax")
  finish
endif

let s:cpo_save = &cpo
set cpoptions&vim

" Syntax clusters
" syntax cluster mailHeaderFields	contains=mailHeaderKey,mailSubject,mailHeaderEmail,@mailLinks,mailNewPart
syntax cluster mailHeaderFields	contains=mailHeaderKey,mailHeaderEmail,@mailLinks,mailNewPart
syntax cluster mailLinks		contains=mailURL,mailEmail
syntax cluster mailQuoteExps	contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

syntax case match
" execute 'syntax region mailHeader contains=@mailHeaderFields,@NoSpell start=''^'. escape(escape(escape(escape(getline(1), '\'), '['), ''''), '/') . '$'' skip=''^\s'' end=''^[^:]*$''me=s-1 fold'
syntax region	mailHeader	contains=@mailHeaderFields,@NoSpell start='^.\+\t\n' end='^[^:]*\n' fold
syntax region	mailHeader	contains=@mailHeaderFields,@NoSpell start='^[\x0C].\+ part\n' end='^\n' fold

" Nothing else depends on case.
syntax case ignore

" Usenet headers
syntax match	mailHeaderKey	contained contains=mailHeaderEmail,mailEmail,@NoSpell '\v^[a-z-]+:\s*'
syntax match	mailNewPart	contains=@mailHeaderFields,@NoSpell '^[\x0C]\zs.\+ part'


" syntax region	mailHeaderKey	contained contains=mailHeaderEmail,mailEmail,@mailQuoteExps,@NoSpell start='\v(^(\> ?)*)@<=(to|b?cc):' skip=',$' end='$'
" syntax match	mailHeaderKey	contained contains=mailHeaderEmail,mailEmail,@NoSpell '\v(^(\> ?)*)@<=(from|reply-to):.*$' fold
" syntax match	mailHeaderKey	contained contains=@NoSpell '\v(^(\> ?)*)@<=date:'
" syntax match	mailSubject	contained "\v^subject:.*$" fold
" syntax match	mailSubject	contained contains=@NoSpell '\v(^(\> ?)+)@<=subject:.*$'

" Anything in the header between < and > is an email address
syntax match	mailHeaderEmail	contained contains=@NoSpell '<.\{-}>'

" Mail Signatures. (Begin with "-- ", end with change in quote level)
syntax region	mailSignature	keepend contains=@mailLinks,@mailQuoteExps start='^--\s$' end='^$' end='^\(> \?\)\+' fold
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
syntax region	mailQuoted6	keepend contains=mailVerbatim,mailHeader,@mailLinks,mailSignature,@NoSpell start='^\z(\(\([a-z]\+>\|[]}>]\)[ \t]*\)\{5}\([a-z]\+>\|[]}>]\)\)' end='^\z1\@!' fold
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
highlight					 mailNewPart		term=reverse,bold gui=reverse,bold
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

let &cpo = s:cpo_save
unlet s:cpo_save
