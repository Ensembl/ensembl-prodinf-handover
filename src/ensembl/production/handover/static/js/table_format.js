function expandIcon(value, row , index){
  return '<span title="Click for more info" style="cursor: pointer; color:blue" class="fas fa-plus" onclick="row_details('+ index +')">+</span> <span class="fa fa-plus"></span>'
}

function row_details(id){
 let table = $('#table');
 console.log(table);
 table.bootstrapTable('expandRow', id);
}
function FormatHandover(index, row){
  return `<a target="_blank" rel="noopener noreferrer" href="/handovers/${row.handover_token}">${row.handover_token}</a>`;
}
function detailFormatter(index, row) {
  $.ajax({
    url: '/handovers/' + row.handover_token + '?format=json',
    success: function (result) {
      HandoverBaseInfo(result[0]);
    },
    error: function (){
      //alert(`unable to retrive data for handover ${row.handover_token}`)
      $(`#${row.handover_token}`).html(`<div class="alert alert-danger m-4" role="alert">
              unable to retrive data for handover ${row.handover_token}
           </div>`);
    }
    //async: false
});
   return `
          <div class="row n-4" id="${row.handover_token}">
            <div class="spinner-border text-primary" role="status">
               <span class="sr-only">Loading...</span> 
            </div>
            Loading....
          </div>
          ` ; 
}

function HandoverBaseInfo(handover_details){
 
  const sucess = new RegExp('^(.+)Handover'+'(.+){1}'+'successful$');
  const failure = new RegExp('^(.+)failed(.+)$');
  const problems = new RegExp('^(.+)problems(.+)$');
  const meta_data_failed = new RegExp('^Metadata(.+)failed(.+)');
  //for testing 
  /*handover_details = {
    "comment": "Updated Refseq xrefs and MANE_Select attributes", 
    "contact": "jmgonzalez@ebi.ac.uk", 
    "handover_token": "6727f4a6-d663-11ea-afbd-005056ab00f0", 
    "id": "YkG2SngBmi1dIqxAz48N", 
    "message": "Metadata load failed, please see http://eg-prod-01.ebi.ac.uk:7003/jobs/5316?format=failures", 
    "progress_complete": 1, 
    "progress_total": 3, 
    "report_time": "2021-03-19T13:39:57.816", 
    "src_uri": "mysql://ensro@mysql-ens-havana-prod-2:4682/homo_sapiens_otherfeatures_104_38", 
    "tgt_uri": "mysql://ensprod:s3cr3t@mysql-ens-sta-1:4519/homo_sapiens_otherfeatures_104_38"
  };*/
    
  let job_status = urlify(handover_details.message);

  if(meta_data_failed.test(handover_details.message)){
    $('#status').show();
  }
  if(sucess.test(handover_details.message) ){
    job_status = `<div class="alert alert-success" role="alert">
                    ${job_status}
                 </div>`;
  }
  else if(failure.test(handover_details.message) || problems.test(handover_details.message) ){
    job_status = `<div class="alert alert-danger" role="alert">
                    ${job_status}
                 </div>`;
  }else{
    const progress = (+handover_details.progress_complete / +handover_details.progress_total) * 100  ;
  
    job_status = `
                  <div class="alert alert-warning" role="alert">
                    ${job_status}
                  </div>
                  <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" role="progressbar" style="width: ${progress}%" 
                    aria-valuenow="0" aria-valuemin="0" aria-valuemax="${handover_details.progress_total}">
                    ${handover_details.progress_complete} / ${handover_details.progress_total} tasks done..
                    </div>
                  </div>
                  `;
  }
  let base_html= `
  <div class="row m-2" >
  <div class="col-12 m-1">
  <div class="card m-1" style="justify-content: center;">
    <div class="card-header">
      Details
    </div>
    <div class="card-body">
    <table class="table ">
    <tbody>
      <tr>
        <td class="bg-secondary">DB</td>
        <td>${handover_details.src_uri}</td>
      </tr>
      <tr>
        <td class="bg-secondary">Date</td>
        <td>${handover_details.report_time}</td>
      </tr>
      <tr>
        <td class="bg-secondary">Email</td>
        <td>${handover_details.contact}</td>
      </tr>
      <tr>
        <td class="bg-secondary">Job status:</td>
        <td>${job_status}</td>
      </tr>
    </tbody>
    </table>
    </div>
  </div>
  </div>
  </div>`;

  $(`#${handover_details.handover_token}`).html(base_html);
}


function statusFormat(value, row){

  const sucess = new RegExp('^(.+)Handover'+'(.+){1}'+'successful$');
  const failure = new RegExp('^(.+)failed(.+)$');
  const problems = new RegExp('^(.+)problems(.+)$');

  if (sucess.test(row.current_message)){
    return ('<span class="badge badge-success">Complete</span><br></br>');
  }
  else if(failure.test(row.current_message) || problems.test(row.current_message)){
    return ('<span class="badge badge-danger">Failed</span><br></br>');
  }
  else{
    return ('<span class="badge badge-info">running</span><br></br>');
  }

}

function urlify(text){

  var url = new RegExp('(.+)http://(.+)');
		var urlRegex = /(https?:\/\/[^\s]+)/g;
		if (url.test(text)){
          return text.replace(urlRegex, function(url) {
                return '<a target="_blank" rel="noopener noreferrer" href="' + url + '">' + url + '</a>';
		    });
		}
		else {
			return(text);
		}
}



















