/* .. See the NOTICE file distributed with this work for additional information
    regarding copyright ownership.
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
        https://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

function expandIcon(value, row, index) {
    return '<span title="Click for more info" style="cursor: pointer; color:blue" class="fas fa-plus" onclick="row_details(' + index + ')">+</span> <span class="fa fa-plus"></span>'
}

function row_details(id) {
    let table = $('#table');
    console.log(table);
    table.bootstrapTable('expandRow', id);
}

function FormatHandover(index, row) {
    return `<a rel="noopener noreferrer" href="/${script_name}/jobs/${row.handover_token}">${row.handover_token}</a>`;
}

function detailFormatter(index, row) {
    $.ajax({
        url: `/api/${script_name}/jobs/${row.handover_token}?format=json`,
        headers: {'Content-Type': 'application/json'},
        success: function (result) {
            HandoverBaseInfo(result[0]);
        },
        error: function () {
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
          `;
}

function HandoverBaseInfo(handover_details) {

    const success = new RegExp('^(.+)Handover' + '(.+){1}' + 'successful$');
    const failure = new RegExp('^(.+)failed(.+)$');
    const problems = new RegExp('^(.+)problems(.+)$');
    const meta_data_failed = new RegExp('^Metadata(.+)failed(.+)');

    let job_status = handover_details.message;

    if (meta_data_failed.test(handover_details.message)) {
        $('#status').show();
    }
    if (success.test(handover_details.message)) {
        job_status = `<div class="alert alert-success" role="alert">${job_status}</div>`;
    } else if (failure.test(handover_details.message) || problems.test(handover_details.message)) {
        job_status = `<div class="alert alert-danger" role="alert">${job_status}</div>`;
    } else {
        const progress = ((handover_details.progress_complete + 1) / handover_details.progress_total) * 100;
        let job_progress = '';

        if ('job_progress' in handover_details) {
            job_progress = `
        <div class="m-1 align-content-end">
          <div class="alert alert-block" role="alert">
            <span class="badge badge-warning">
              Running <span class="badge badge-light">${handover_details.job_progress.inprogress}</span>
            </span>
            <span class="badge badge-success">
              Completed <span class="badge badge-light">${handover_details.job_progress.completed}</span>
            </span>
            <span class="badge badge-danger">
              Failed <span class="badge badge-light">${handover_details.job_progress.failed}</span>
            </span>  
          </div>  
        </div>
        `;
        }
        job_status = `
      <div class="alert alert-info" role="alert">
        ${job_status}
        ${job_progress}
          <div class="progress">
            <div class="progress-bar progress-bar-striped progress-bar-animated bg-info" role="progressbar" 
                style="width: ${progress}%"  aria-valuenow="${handover_details.progress_complete}+1" aria-valuemin="0" 
                aria-valuemax="${handover_details.progress_total}">
            ${handover_details.progress_complete + 1} / ${handover_details.progress_total} tasks
            </div>
          </div>
      </div>
      `;
    }
    let base_html = `
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
  </div>
  `;

    $(`#${handover_details.handover_token}`).html(base_html);
}


function statusFormat(value, row) {

    const sucess = new RegExp('^(.+)Handover' + '(.+){1}' + 'successful$');
    const failure = new RegExp('^(.+)failed(.+)$');
    const problems = new RegExp('^(.+)problems(.+)$');
    const running_job = new RegExp('.*(Handling|Datachecks|metadata|Copying|Dispatching)\\s?.+');

    if (sucess.test(row.current_message)) {
        return ('<span class="badge badge-success">Complete</span><br></br>');
    } else if (failure.test(row.current_message) || problems.test(row.current_message)) {
        return ('<span class="badge badge-danger">Failed</span><br></br>');
    } else {
        let datacheck_job_progress = '';
        if ('job_progress' in row) {
            let progress_count = Math.ceil((+row.job_progress.completed / +row.job_progress.total) * 100) || 0;
            datacheck_job_progress = `
                <div class="progress mt-2" style="min-width: 100px">
                    <div class="progress-bar progress-bar-striped" role="progressbar" aria-valuenow="${progress_count}" aria-valuemin="0"
                        aria-valuemax="100" style="width: ${progress_count}%; background-color:rgb(72, 221, 104) !important;">
                        <span class="sr-only">${progress_count}% Complete</span>
                    </div>
                    <span class="progress-type">DC</span>
                    <span class="progress-completed">${progress_count}%</span>
                </div>`;
        }
        let job_in_progess = running_job.exec(row.current_message);
        if (job_in_progess != null) {
            job_in_progess = "Running";
        } else {
            job_in_progess = "Unknown status";
        }
        return (`<div class="badge badge-info">${job_in_progess}</div>
                ${datacheck_job_progress}`);
    }
}

function urlify(text) {

    var url = new RegExp('(.+)https://(.+)');
    var urlRegex = /(https?:\/\/[^\s]+)/g;
    if (url.test(text)) {
        return text.replace(urlRegex, function (url) {
            return '<a target="_blank" rel="noopener noreferrer" href="' + url + '">' + url + '</a>';
        });
    } else {
        return (text);
    }
}



















