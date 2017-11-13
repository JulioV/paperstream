(function encodeDiary() {
  // init canvas
  const canvas = new fabric.Canvas('c');

  function initCanvasParams() {
    // stage dimensions
    canvas.stageWidth = 570;
    canvas.stageHeight = 920;

    canvas.entryHeight = 200;
    canvas.markSize = 12;

    // global index of entries
    canvas.entries = {};
    // global id for entries
    canvas.entriesID = 0;
    // global id for mark areas
    canvas.markAreasID = 0;
    // toogle to add or not marking areas
    canvas.toogleAnswerSpace = false;
  }

  // Get today's date in format DD/MM/2017
  function getTodayDate() {
    const today = new Date();
    let dd = today.getDate();
    let mm = today.getMonth() + 1; // January is 0!

    const yyyy = today.getFullYear();
    if (dd < 10) { dd = `0${dd}`; }
    if (mm < 10) { mm = `0${mm}`; }

    return `${dd}/${mm}/${yyyy}`;
  }

  initCanvasParams();

  const diariesToEncode = [];
  const customElement = $('<div>', {
    id: 'countdown',
    css: {
      padding: '200px 0 0 0',
      'font-size': '30px',
    },
    text: '',
  });

  // Avoid accidental back clicks and loosing data
  window.addEventListener('beforeunload', (e) => {
    (e || window.event).returnValue = null;
    return null;
  });

  function toogleUIComponents(toogle) {
    $('#toogleAnswerSpace').attr('disabled', toogle);
    $('#encodeDiaries').attr('disabled', toogle);
    $('#duplicateEntry').attr('disabled', toogle);
    $('#downloadCanvasBackup').attr('disabled', toogle);
    $('#variable').attr('disabled', toogle);
    $('#value').attr('disabled', toogle);
  }

  canvas.on('mouse:down', (options) => {
    // Add mark areas
    if (canvas.toogleAnswerSpace && options.target !== undefined && options.target.type === 'entry') {
      const variable = ($('#variable').val());
      const value = ($('#value').val());
      const entry = options.target;
      const pointer = canvas.getPointer(options.e);
      const posX = pointer.x;
      const posY = pointer.y;
      entry.createAnswerSpace(
        posX - (canvas.markSize),
        posY - (canvas.markSize),
        variable,
        value,
      );
    }
  });

  canvas.on('mouse:dblclick', (options) => {
    if (options.target !== undefined && options.target.type === 'mark') {
      // Delete answer spaces
      const answerSpace = options.target;
      delete answerSpace.entry.answerSpaces[answerSpace.markID];
      answerSpace.entry = null; // does this prevent a memory leak?
      canvas.remove(answerSpace);
    } else if (options.target !== undefined && !canvas.toogleAnswerSpace && options.target.type === 'entry') {
      // Delete entry and its answer spaces
      const entry = options.target;
      Object.entries(entry.answerSpaces).forEach(([key, answerSpace]) => {
        canvas.remove(answerSpace);
        delete entry.answerSpaces[key];
      });

      delete canvas.entries[entry.entryID];
      canvas.remove(entry);

      $(`#entries_combo option[value='${entry.entryID}']`).remove();
      if (Object.keys(canvas.entries).length < 1) {
        toogleUIComponents(true);
        $('#entries_combo').append('<option value="default">Add an entry first...</option>');
        $('#toogleAnswerSpace').text('Start Adding Mark Areas');
      }
    }
  });

  function createEntry(x, y) {
    // Enable relevant buttons
    toogleUIComponents(false);

    // Create entry object
    const entry = new fabric.Rect({
      left: x,
      top: y,
      fill: 'rgba(0,0,0,0)',
      strokeDashArray: [5, 5],
      stroke: 'red',
      strokeWidth: 3,
      width: 555,
      height: canvas.entryHeight,
      entryID: canvas.entriesID,
      answerSpaces: {},
      type: 'entry',
    });

    // Method executed to check if there are duplicate variable/value pairs
    entry.containsVariableValue = function containsVariableValue(variable, value) {
      for (area in this.answerSpaces)
        {if (this.answerSpaces[area].variable === variable && this.answerSpaces[area].value === value)
          return true;}
      return false;
    };

    // Method executed to create a mark area
    entry.createAnswerSpace = function createAnswerSpace(xSpace, ySpace, variable, value) {
      if (this.containsVariableValue(variable, value)) {
        new Noty({
          text: 'Duplicated answer space. Change VARIABLE or VALUE.',
          type: 'warning',
          theme: 'metroui',
        }).show();
        return false;
      }


      const area = new fabric.Circle({
        left: xSpace,
        top: ySpace,
        fill: 'rgba(255,0,0,0.3)',
        stroke: 'blue',
        strokeWidth: 2,
        radius: canvas.markSize,
        borderColor: 'orange',
        cornerColor: 'black',
        cornerSize: 3,
        padding: 10,
        transparentCorners: false,
        hasControls: true,
        type: 'mark',
        entry: this,
        markID: canvas.markAreasID,
        variable,
        value,
      });

      this.answerSpaces[canvas.markAreasID] = area;

      canvas.markAreasID += 1;
      canvas.add(area);
      return true;
    };

    // Update UI
    $("#entries_combo option[value='default']").remove();
    $('#entries_combo').append(`<option value="${canvas.entriesID}"> Entry ${canvas.entriesID}</option>`);

    // Update canvas variable
    canvas.entries[canvas.entriesID] = entry;
    canvas.entriesID += 1;
    canvas.add(entry);
    return entry;
  }

  // Method that creates a new entry shifted in the y axis
  function addEntry() {
    createEntry(0, Math.floor((Math.random() * 70) + 1) + (canvas.entryHeight * 3));
  }

  // If toggle enables the creation of mark areas inside an entry
  function toggleAddingAnswerSpace() {
    if (Object.keys(canvas.entries).length > 0) {
      // Unselect any object
      canvas.discardActiveObject();
      canvas.requestRenderAll();

      // Toogle flag
      canvas.toogleAnswerSpace = this.checked;

      // Send all entries to the back so they are not on top of any old marks
      Object.keys(canvas.entries).forEach(([key]) => {
        canvas.entries[key].selectable = !canvas.toogleAnswerSpace;
        canvas.entries[key].sendToBack();
      });

      // Update UI
      if (canvas.toogleAnswerSpace) {
        $('#labelToogleAnswerSpace').text('STOP Adding Answer Spaces');
      } else {
        $('#labelToogleAnswerSpace').text('Start Adding Answer Spaces');
      }
    }
  }

  // Duplicate an existing entry with all its marks
  function duplicateEntry() {
    const oldEntryID = $('#entries_combo').val();
    if (oldEntryID >= 0) {
      const newEntryTop = canvas.stageHeight - canvas.entryHeight - 50;
      const oldEntryTop = canvas.entries[oldEntryID].top;
      const newEntry = createEntry(0, newEntryTop);

      // Duplicate all markareas of the old entry
      const oldEntryAreas = canvas.entries[oldEntryID].answerSpaces;
      Object.values(oldEntryAreas).forEach((oldEntryArea) => {
        const newMarkTop = (oldEntryArea.top - oldEntryTop) + newEntryTop;
        const newMarkLeft = oldEntryArea.left;
        const newMarkVariable = oldEntryArea.variable;
        const newMarkValue = oldEntryArea.value;
        newEntry.createAnswerSpace(newMarkLeft, newMarkTop, newMarkVariable, newMarkValue);
      });
    }
  }

  // Back the canvas to a CSV file
  function downloadCanvasBackup() {
    canvas.calcOffset();
    let csvContent = 'data:text/csv;charset=utf-8,';
    csvContent += 'entryID,entryX,entryY,variable,value,x,y,radius\n';
    Object.entries(canvas.entries).forEach(([entryID, entry]) => {
      Object.values(entry.answerSpaces).forEach((answerSpace) => {
        csvContent += `${entryID},${entry.left},${entry.top},${answerSpace.variable},${answerSpace.value},${answerSpace.left},${answerSpace.top},${answerSpace.radius}\n`;
      });
    });

    // Trick the browser to download the csv file through a link
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'canvas_backup.csv');
    document.body.appendChild(link); // Required for FF
    link.click(); // This will download the data file named "my_data.csv".
  }

  // Load CSV file that has the canvas backup
  function loadCSVCanvasBackup() {
    function loadCSVComplete(evt) {
      const content = evt.target.result;
      canvas.clear();
      initCanvasParams();

      const lines = $.csv.toObjects(content);
      const processedEntries = [];
      let newEntry = null;
      Object.values(lines).forEach((line) => {
        if (line.entryID >= 0 && processedEntries.indexOf(line.entryID) === -1) {
          newEntry = createEntry(parseFloat(line.entryX), parseFloat(line.entryY));
          processedEntries.push(line.entryID);
        }
        // Create mark
        newEntry.createAnswerSpace(
          parseFloat(line.x),
          parseFloat(line.y),
          line.variable,
          line.value,
        );
      });
      canvas.requestRenderAll();
    }

    const reader = new FileReader();
    reader.readAsText(this.files[0]);
    reader.addEventListener('loadend', loadCSVComplete);
    reader.addEventListener('error', () => {
      new Noty({
        text: 'Error loading CSV file',
        type: 'error',
        theme: 'metroui',
      }).show();
    });
  }

  // Create the encoding rubric built in the Canvas as a string
  function createEncodingRubric() {
    // The CSV format is "entryID,variable,value,x,y,radius\n";
    let csvContent = '';
    Object.entries(canvas.entries).forEach(([entryID, entry]) => {
      Object.values(entry.answerSpaces).forEach((answerSpace) => {
        csvContent += `${entryID},${answerSpace.variable},${answerSpace.value},${answerSpace.left + canvas.markSize},${answerSpace.top + canvas.markSize},${answerSpace.radius}\n`;
      });
    });
    return csvContent.slice(0, -1);
  }

  // Send the diariesToEncode to the server to be encoded, the answers are download in a zip
  function encodeDiaries() {
    const rubric = createEncodingRubric();

    const date = $('#date').val();
    const answersToDownload = [];


    $.LoadingOverlay('show', {
      custom: customElement,
    });

    // Executes a post request to /encode_diary for each item in diariesToEncode
    async.eachOfSeries(
      diariesToEncode, (item, key, itemCompleted) => {
        customElement.text(`Encoding diary ${key + 1}/${diariesToEncode.length}. Please wait and don't refresh the page`);
        $.post(
          '/encode_diary',
          JSON.stringify({
            diary: item,
            rubric,
            date,
          }),
        ).done((data) => {
          answersToDownload.push(data);
          itemCompleted(null);
        }).fail((xhr, status, individualError) => {
          new Noty({
            text: `Error encoding ${item}. Message: ${individualError}`,
            type: 'error',
            theme: 'metroui',
          }).show();
          itemCompleted(individualError);
        });
      },
      // When all the encoding is done
      (globalError) => {
        $.LoadingOverlay('hide');
        if (globalError != null) {
          // error
          new Noty({
            text: `Error encoding the diaries. Message: ${globalError}`,
            type: 'error',
            theme: 'metroui',
          }).show();
        } else {
          // Ask the server to zip all the encoding diaries (CSV files)
          $.post(
            '/download_files',
            JSON.stringify({
              files: answersToDownload,
              name: 'answers.zip',
            }),
          ).done((data) => {
            // Trick the browser to download the zip with a link
            const a = document.createElement('a');
            a.href = `/${data.file}`;
            a.download = 'answers.zip';
            a.style.display = 'none';
            document.body.appendChild(a);
            a.click();
          }).fail((xhr, status, errorZip) => {
            new Noty({
              text: `Error creating zip file. Message: ${errorZip}`,
              type: 'error',
              theme: 'metroui',
            }).show();
          }); // fail
        } // else
      }, // eachOfSeries arguments
    ); // eachOfSeries
  }

  // Init GUI
  $(document).ready(() => {
    // Hook click listeners
    $('#duplicateEntry').click(duplicateEntry);
    $('#addEntry').click(addEntry);
    $('#toogleAnswerSpace').change(toggleAddingAnswerSpace);
    $('#downloadCanvasBackup').click(downloadCanvasBackup);
    $('#loadCSVCanvasBackup').change(loadCSVCanvasBackup);
    $('#encodeDiaries').click(encodeDiaries);

    // Disable buttons that need some extra information
    toogleUIComponents(true);

    // Populate textboxes
    $('#date').val(getTodayDate());
    $('#variable').val('time');
    $('#value').val('12');

    // Get the list of diaries to encode
    $.get('/scanned_diaries').done((data) => {
      if (data.diaries.length < 1) {
        $('#diariesToEncode').append('<li> Make sure your scanned diaries (tiff) are in input/3_diaries_to_encode/</li>');
        $('#encodeDiaries').attr('disabled', true);
      }
      Object.values(data.diaries).forEach(diary => $('#diariesToEncode').append(`<li>${diary}</li>`));
      Object.values(data.diaries_paths).forEach(diaryPath => diariesToEncode.push(diaryPath));
    });
  });
}());
