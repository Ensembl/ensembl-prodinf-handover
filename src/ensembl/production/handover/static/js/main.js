$(function () {

    // set style sheet as per handover 

    console.log('Handover autocomplete');
    var SelectedHostDetails;

    console.log(copy_url);

    $("#src_uri").autocomplete({
        source: function (request, response) {
            $.ajax({
                url: `${script_name}/jobs/dropdown/src_host`,
                dataType: "json",
                data: {
                    name: request.term
                },
                success: function (data) {
                    console.log('success...........');
                    response($.map(data.results, function (item) {
                        return item;
                    }));

                }
            });
        },
        minLength: 1,
        select: function (event, ui) {

             
            if(ui.item.active){
              SelectedHostDetails = ui.item ;    
              this.value = 'mysql://'+ ui.item.mysql_user + '@' + ui.item.name + ':' + ui.item.port + '/';
            }
            return false;
        },
        change: function (event, ui) {

        }
    }).data( "ui-autocomplete" )._renderItem = function( ul, item ) {
        let active = 'badge-danger';
        let desc = 'Not Active';
        if(item.active){
          active = 'badge-success';
          desc = 'Active'
        }
        return $( "<li>" )
        .append( '<span class="badge badge-pill '+  active + '">'+ desc+'</span> <span>' + item.name +'</span>')
        .appendTo( ul );
    };
    //add dblist dropdown
    $("#database").autocomplete({
        source: function (request, response) {
            $.ajax({
                url: `${script_name}/jobs/dropdown/databases/${SelectedHostDetails.name}/${SelectedHostDetails.port}`,
                // url: `/dropdown/databases/${SelectedHostDetails.name}/${SelectedHostDetails.port}`,
                dataType: "json",
                data: {
                    search: request.term
                },
                success: function (data) {

                    response(data);
                },
                error: function (_request, _textStatus, _error) {
                  response([]);
                }
            });
        },
        minLength: 1,
        select: function (event, ui) {
            this.value =  ui.item.value;
            return false;
        },
        change: function () {
            
        }
    });

});