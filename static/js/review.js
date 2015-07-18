$(function() {
    var segdata = [];

    var imgw = 3510.0;
    var imgh = 2482.0;

    var img = document.getElementById('pageimage');
    var img_cw = img.clientWidth;
    var img_ch = 827;

    var scale_x = img_cw / imgw;
    var scale_y = img_ch / imgh;

    var highlight = $('#highlight');
    var overlay = $('#overlay');
    var ocrtext = $('#ocrtext');
    var usertext = $('#usertext');
    var suggestions = $('#suggestions');

    var lastrevid = null;
    var segno = -1;

    function setbox(seg) {
        var x1 = Math.round(seg.x1 * scale_x);
        var y1 = Math.round(seg.y1 * scale_y);
        var x2 = Math.round(seg.x2 * scale_x);
        var y2 = Math.round(seg.y2 * scale_y);

        highlight.css('top', '' + y1-1 + 'px');
        highlight.css('left', '' + x1-1 + 'px');
        highlight.css('width', '' + (x2-x1+1) + 'px');
        highlight.css('height', '' + (y2-y1+1) + 'px');

        overlay.css('top', '' + y1 + 'px');
        overlay.css('margin-right', '25%');
        console.log('Block: ' + x1 + ',' + y1 + ' - ' + x2 + ','+ y2 + 'px');
        usertext.val(seg.text);
        usertext.attr('rows', String(seg.textlines));
        ocrtext.text(seg.ocrtext);

        suggestions.empty();
        seg.suggests.forEach(function(s){
            var linktxt = (s.length ? s : "(blank)");
            var n = $("<li><a>"+linktxt+"</a></li>");
            n.click(function() { usertext.val(s); });
            suggestions.append(n);
        });

        document.getElementById("usertext").focus();
        window.scrollTo(0, y1-300);
    }

    function nextsegment() {
        if (segno >= 0) {
            $('#undobutton').attr('enabled', true);
        }
        if (segno < segdata.length-1) {
            segno++;
            var seg = segdata[segno];
            $(img).css('background', 'url(/doc/cached/' + seg.docid + '/'+ seg.page + ')');
            $(img).css('background-size', '1170px');
            $(img).css('background-repeat', 'no-repeat');
            setbox(seg);
            highlight.css('display', 'inline');
            overlay.css('display', 'inline');
        }
        checkfornextpage();
    }

    function checkfornextpage(startup) {
        if (segno >= segdata.length-1) {
            // Load up the next page
            $.get('/api/reviewdata').done(function(data) {
                segdata = segdata.concat(data.segments);
                if (startup) {
                    nextsegment();
                }
            });
            return true;
        }
        return false;
    }

    $('#undobutton').click(function(e) {
        if (!segno) {
            return;
        }

        $.get('/api/unreview/' + segdata[segno-1].segment_id, {revid: lastrevid}).done(function() {
            segno -= 2;
            nextsegment();
        });

        e.preventDefault();
    });

    $('#skipbutton').click(function(e) {
        lastrevid = null;
        $.get('/api/review/' + segdata[segno].segment_id, {skip: true}).fail(function() {
            // TODO: Handle AJAX error.
        });
        nextsegment();
        e.preventDefault();
    });

    $('#savebutton').click(function(e) {
        var newtxt = usertext.val();
        segdata[segno].text = newtxt;
        $.get('/api/review/' + segdata[segno].segment_id, {text: newtxt}).done(function (data) {
            if (data.status === 'ok') {
                lastrevid = data.id;
            } else {
                // TODO: Handle backend error.
            }
        }).fail(function() {
            // TODO: Handle AJAX error.
        });
        nextsegment();
        e.preventDefault();
    });

    var hotkeys = [
        {key: 'ctrl+return', btn: '#savebutton'},
        {key: 'ctrl+z', btn: '#undobutton'},
        {key: 'ctrl+s', btn: '#skipbutton'}];

    hotkeys.map(function(kmap) {
        usertext.bind('keydown', kmap.key, function () { $(kmap.btn).click(); return false; });
        $(document).bind('keydown', kmap.key, function () { $(kmap.btn).click(); return false; });
    });

    checkfornextpage(true);
});
