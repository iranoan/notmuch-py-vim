" notmuch-draft/show common part
scriptversion 4

" Syntax clusters
syntax cluster	mailHeaderField	contains=mailHeaderEmail,@mailLinks,@mailHeaderComp
syntax cluster	mailLinks	contains=mailURL,mailEmail
syntax cluster	mailQuoteExps	contains=mailQuoteExp1,mailQuoteExp2,mailQuoteExp3,mailQuoteExp4,mailQuoteExp5,mailQuoteExp6

" Usenet headers
syntax match	mailHeaderKey	contained	contains=mailHeaderEmail,mailEmail,@NoSpell /\v^[a-z-]+:\s*/

syntax region	mailHeader	contains=mailHeaderKey,mailHideHeader,@mailHeaderField,@NoSpell start='\%^' skip='^\s' end='^$'me=s-1 end='^[\x0C]'me=e-1 fold
execute 'syntax region	mailHideHeader	contained	contains=mailHeaderKey,@mailHeaderField,@NoSpell,@mailHeaderComp '
			\ .. 'start=''^\%(' .. py3eval('get_hide_header()') .. '\):'' skip=''^\s'' '
			\ .. 'end=''' .. '^\%(' .. join(g:notmuch_show_headers, '\|') .. '\|\%(Del-\)\?\%(Attach\|HTML\)\|Fcc\|\%(Not-\)\?Decrypted\|Encrypt\|\%(Good-\|Bad-\)\?Signature\):''me=s-1 '
			\ .. 'end=''^$'' fold'

" Anything in the header between < and > is an email address
syntax match	mailHeaderEmail	contained	contains=@NoSpell '<.\{-}>'

" Mail Signatures. (Begin with "-- ", end with change in quote level)
syntax region	mailSignature keepend	contains=@mailLinks,@mailQuoteExps start='^--\s$' end='^$' end='^\%(> \?\)\+'me=s-1 fold
syntax region	mailSignature keepend	contains=@mailLinks,@mailQuoteExps,@NoSpell start='^\z(\%(> \?\)\+\)--\s$' end='^\z1$' end='^\z1\@!'me=s-1 end='^\z1\%(> \?\)\+'me=s-1 fold

" Treat verbatim Text special.
syntax region	mailVerbatim	keepend	contains=@NoSpell start='^#v+$' end='^#v-$' fold
syntax region	mailVerbatim	keepend	contains=@mailQuoteExps,@NoSpell start='^\z(\%(> \?\)\+\)#v+$' end='\z1#v-$' fold

" URLs start with a known protocol or www,web,w3.
syntax match	mailURL	contains=@NoSpell '\v(<(((https?|ftp|gopher)://|(mailto|file|news):)[^'' \t<>"]+|(www|web|w3)[a-z0-9_-]*\.[a-z0-9._-]+\.[!#-&*-;=?-Z\\^-z|~]+)[a-z0-9/])'

syntax match	mailEmail	contains=@NoSpell '\v[_=a-z\./+0-9-]+\@[a-z0-9._-]+\a{2}'

" Make sure quote markers in regions (header / signature) have correct color
syntax match	mailQuoteExp1	contained '\v^[ \t]*(\> ?)'
syntax match	mailQuoteExp2	contained '\v^[ \t]*(\> ?){2}'
syntax match	mailQuoteExp3	contained '\v^[ \t]*(\> ?){3}'
syntax match	mailQuoteExp4	contained '\v^[ \t]*(\> ?){4}'
syntax match	mailQuoteExp5	contained '\v^[ \t]*(\> ?){5}'
syntax match	mailQuoteExp6	contained '\v^[ \t]*(\> ?){6}'

" Even and odd quoted lines. Order is important here!
syntax region	mailQuoted6	keepend	contains=mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*\%(\%([a-z]\+>\|[]>]\)[ \t]*\)\{5}\%([ \t]*[a-z]\+>\|[ \t]*[]>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted5	keepend	contains=mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*\%(\%([a-z]\+>\|[]>]\)[ \t]*\)\{4}\%([ \t]*[a-z]\+>\|[ \t]*[]>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted4	keepend	contains=mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*\%(\%([a-z]\+>\|[]>]\)[ \t]*\)\{3}\%([ \t]*[a-z]\+>\|[ \t]*[]>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted3	keepend	contains=mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*\%(\%([a-z]\+>\|[]>]\)[ \t]*\)\{2}\%([ \t]*[a-z]\+>\|[ \t]*[]>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted2	keepend	contains=mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*\%(\%([a-z]\+>\|[]>]\)[ \t]*\)\{1}\%([ \t]*[a-z]\+>\|[ \t]*[]>]\)\)' end='^\z1\@!' fold
syntax region	mailQuoted1	keepend	contains=mailQuoted2,mailQuoted3,mailQuoted4,mailQuoted5,mailQuoted6,mailVerbatim,mailHeader,mailHeader2,@mailLinks,mailSignature,@NoSpell start='^\z([ \t]*[a-z]\+>\|[ \t]*[]>]\)' end='^\z1\@!' fold

" Need to sync on the header. Assume we can do that within 100 lines
if exists('mail_minlines')
	execute 'syn sync minlines=' .. mail_minlines
else
	syntax sync minlines=100
endif

" Define the default highlighting.
highlight default link mailVerbatim	Special
highlight default link mailHeader	Statement
highlight default link mailHideHeader	mailHeader
highlight default link mailHeaderKey	Type
highlight default link mailSignature	PreProc
highlight default link mailHeaderEmail mailEmail
highlight default link mailEmail	Special
highlight default link mailURL	String
highlight default link mailQuoted1	Comment
highlight default link mailQuoted2	Identifier
highlight default link mailQuoted3	mailQuoted1
highlight default link mailQuoted4	mailQuoted2
highlight default link mailQuoted5	mailQuoted1
highlight default link mailQuoted6	mailQuoted2
highlight default link mailQuoteExp1	mailQuoted1
highlight default link mailQuoteExp2	mailQuoted2
highlight default link mailQuoteExp3	mailQuoted3
highlight default link mailQuoteExp4	mailQuoted4
highlight default link mailQuoteExp5	mailQuoted5
highlight default link mailQuoteExp6	mailQuoted6
highlight mailNewPartHead term=reverse,bold gui=reverse,bold
