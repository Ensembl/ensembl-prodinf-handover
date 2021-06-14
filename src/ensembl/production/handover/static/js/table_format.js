/* .. See the NOTICE file distributed with this work for additional information
    regarding copyright ownership.
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        http://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/
    
function expandIcon(value, row , index){
  return '<span title="Click for more info" style="cursor: pointer; color:blue" class="fas fa-plus" onclick="row_details('+ index +')">+</span> <span class="fa fa-plus"></span>'
}

function row_details(id){
 let table = $('#table');
 console.log(table);
 table.bootstrapTable('expandRow', id);
}
function FormatHandover(index, row){
  return `<a rel="noopener noreferrer" href="/jobs/${row.handover_token}">${row.handover_token}</a>`;
}
function detailFormatter(index, row) {
  $.ajax({
    url: '/jobs/' + row.handover_token + '?format=json',
    success: function (result) {
      HandoverBaseInfo(result[0]);
    },
    error: function (){
      $(`#${row.handover_token}`).html(`<div class="alert alert-danger m-4" role="alert">
              unable to retrive data for handover ${row.handover_token}
           </div>`);
    }
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
    let job_progress = '';

    if ('job_progress' in handover_details ) {
      job_progress = `
        <div class="row m-2">
          <div class="alert alert-dark" role="alert">DataCheck:
            <span class="badge badge-warning">
              Jobs Running <span class="badge badge-light">${handover_details.job_progress.inprogress}</span>
            </span>
            <span class="badge badge-success">
              Jobs completed <span class="badge badge-light">${handover_details.job_progress.completed}</span>
            </span>
            <span class="badge badge-danger">
              Jobs Failed <span class="badge badge-light">${handover_details.job_progress.failed}</span>
            </span>  
          </div>  
        </div>
        `;
    }  
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
      <div>
        ${job_progress}
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



















