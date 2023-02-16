function JsonToCSV(objArray) {
    var array = typeof objArray != 'object' ? JSON.parse(objArray) : objArray;
    var str = ''; 
    let line = ''; 
    //set the header field
    for(let header in array[1] ){
        line += header + ','
    }
    str += line + '\r\n';
    for (var i = 1; i < array.length; i++) {
        console.log(array[i])
        line = '';
        for(let each_val in array[i] ){
            console.log(each_val)
            console.log(array[i][each_val])
            let val = '';
            if (array[i][each_val] != undefined && typeof array[i][each_val] != 'object' && array[i][each_val] != '' ) {
                val = array[i][each_val].replace(/,/g, '')
                line += val+','
            }

        }
        console.log(line);
        str += line + '\r\n';
    }

    return str;
}

function exportCSVFile(headers, items, fileTitle) {
    if (headers) {
        items = [headers, ...items];
    }
    var jsonObject = JSON.stringify(items);
    var csv = this.JsonToCSV(items);
    console.log(csv); 
    var exportedFilenmae = fileTitle + '.csv' || 'export.csv';

    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, exportedFilenmae);
    } else {
        var link = document.createElement("a");
        if (link.download !== undefined) { // feature detection
            // Browsers that support HTML5 download attribute
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", exportedFilenmae);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
}
