
(function createDiary() {
  const diaryTemplates = [];
  const customElement = $('<div>', {
    id: 'countdown',
    css: {
      padding: '200px 0 0 0',
      'font-size': '30px',
    },
    text: "Creating diary 1/8. Please wait and don't refresh the page",
  });

  // Get today's date in format DD/MM/2017
  function getTodayDate() {
    const today = new Date();
    let dd = today.getDate();
    let mm = today.getMonth() + 1; // January is 0!

    const yyyy = today.getFullYear();
    if (dd < 10) {
      dd = `0${dd}`;
    }
    if (mm < 10) {
      mm = `0${mm}`;
    }
    const stringDate = `${dd}/${mm}/${yyyy}`;
    return stringDate;
  }
  // Executes a post request to /create_diary for each item in diaryTemplates
  function createDiaries() {
    const pages = $('#pages').val();
    const date = $('#date').val();
    const email = $('#email').val();
    const font = $('#font').val();
    const diariesToDownload = [];


    $.LoadingOverlay('show', {
      custom: customElement,
    });

    async.eachOfSeries(
      diaryTemplates, (item, key, itemCompleted) => {
        customElement.text(`Creating diary ${key + 1}/${diaryTemplates.length}. Please wait and don't refresh the page`);
        $.post(
          '/create_diary',
          JSON.stringify({
            pdf_template: item,
            pages,
            date,
            email,
            font,
          }),
        )
          .done((data) => {
            console.log(`finish ${data}`);
            diariesToDownload.push(data);
            itemCompleted(null);
          })
          .fail((xhr, status, error) => {
            console.log(error);
            // console.log(status);
            // console.log(xhr);
            itemCompleted(error);
          });
      },
      // When all diaries are created
      (error) => {
        $.LoadingOverlay('hide');
        if (error != null) {
        // error
          console.log('Error creating diaries');
        } else {
        // Ask the server to zip all the encoding diaries (PDF files)
          $.post(
            '/download_files',
            JSON.stringify({
              files: diariesToDownload,
              name: 'diaries.zip',
            }),
          )
            .done((data) => {
            // Trick the browser to download the zip with a link
              const a = document.createElement('a');
              a.href = `/${data.file}`;
              // Give filename you wish to download
              a.download = 'diaries.zip';
              a.style.display = 'none';
              document.body.appendChild(a);
              a.click();
            })
            .fail((xhr, status, errorZip) => {
              console.log('Error creating zip');
              console.log(errorZip);
              // console.log(status);
              // console.log(xhr);
            });
        }
      },
    );
  }

  $(document).ready(() => {
    $('#createDiaries').click(createDiaries);

    // Get a list of all the templates that will become diaries
    $.get('/pdf_template_diaries').done((data) => {
      if (data.templates_file_names.length < 1) {
        $('#diaries_to_create').append('<li> Make sure the PDF templates for your diaries are in input/1_diaries_to_create/</li>');
        $('#createDiaries').attr('disabled', true);
      }
      Object.entries(data.templates_file_names).forEach(([, value]) => $('#diaries_to_create').append(`<li>${value}</li>`));
      Object.entries(data.templates_paths).forEach(([, value]) => diaryTemplates.push(value));
    });
    $('#pages').val(2);
    $('#date').val(getTodayDate());
  });
}());
