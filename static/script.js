
$(document).ready(function() {

            // Use a "/test" namespace.
            // An application can open a connection on multiple namespaces, and
            // Socket.IO will multiplex all those connections on a single
            // physical channel. If you don't care about multiple channels, you
            // can set the namespace to an empty string.
            namespace = '/test';

            // Connect to the Socket.IO server.
            // The connection URL has the following format:
            //     http[s]://<domain>:<port>[/<namespace>]
            var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port + namespace);

            // Event handler for new connections.
            // The callback function is invoked when a connection with the
            // server is established.
            socket.on('connect', function() {
              socket.emit('connected', {data: 'I\'m connected!'});
            });

            // Event handler for server sent data.
            // The callback function is invoked whenever the server emits data
            // to the client. The data is then displayed in the "Received"
            // section of the page.
            socket.on('my_response', function(msg) {
              $('#zodb_data').html(JSON.stringify(msg, null, "\t"));
              $('#temperature').html(msg.weather.temperature);
              $('#deg').html(msg.deg);
              $('#windspeed').html(msg.weather.windspeed);
              $('#hum').html(msg.hum);
              $('#lux').html(msg.lux);
              $('#emit_data').val(msg.motornord.movetoposition);               
              $('#emit_data2').val(msg.motorsyd.movetoposition); 
              if ( msg.motorsyd.confirm == 'confirm' ) {
                dialog_ventsyd.dialog("open");
              } 
              if ( msg.motornord.confirm == 'confirm' ) {
                dialog_ventnord.dialog("open");
              }
              if ( msg.VentAutSwitch ) {
                $(".vent").hide("fast");
                $( "#data" ).prop( "checked", true );
              }
              if ( msg.motornord.cleanstate == true) {
                $('#motornordState').text("Stilla");
              } else {
                $('#motornordState').text("Kör");
              }
              if ( msg.motorsyd.cleanstate == true) {
                $('#motorsydState').text("Stilla");
              } else {
                $('#motorsydState').text("Kör");
              }

              var elem = document.getElementById("nordBar");   
              var width = msg.motornord.position / msg.motornord.ranger * 100;
              elem.style.width = width + '%'; 
              elem.innerHTML = Math.trunc(width * 1)  + '%';
              

              var elem2 = document.getElementById("sydBar");   
              var width2 = msg.motorsyd.position / msg.motorsyd.ranger * 100;
              elem2.style.width = width2 + '%'; 
              elem2.innerHTML = Math.trunc(width2 * 1)  + '%';
              
            });


            // Handlers for the different forms in the page.
            // These accept data from the user and send it to the server in a
            // variety of ways
            $('form#ventautswtich').change(function(event) {
              socket.emit('data_send', {VentAutSwitch: $('#data').is(':checked')});
              $(".vent").toggle("fast");
              return false;
            });
            $('form#ventnord').change(function(event) {
              socket.emit('data_send', {motornord: {movetoposition: $('#emit_data').val()}});
              return false;
            });
            $('form#ventsyd').change(function(event) {
              socket.emit('data_send', {motorsyd: {movetoposition:  $('#emit_data2').val()}});
              return false;
            });
            $('form#tempsetpointday').change(function(event) {
              socket.emit('data_send', {TempSetPointDay: $('#d').val()});
              return false;
            });
            $('form#tempsetpointnight').change(function(event) {
              socket.emit('data_send', {tempsetpointnight: $('#d2').val()});
              return false;
            });
            $('form#heatersetpoint').change(function(event) {
              socket.emit('data_send', {heatersetpoint: $('#emit_data').val()});
              return false;
            });
            $('form#tempsetpointheater').change(function(event) {
              socket.emit('data_send', {TempSetPointHeater: $('#myRange4').val()});
              return false;
            });
            $('form#heaterswitch').change(function(event) {
              socket.emit('data_send', {HeaterSwitch: $('#data2').is(':checked')});
              return false;
            });
            $('form#A_W1').change(function(event) {
              socket.emit('data_send', {watering: {A: {W1: $('#A_W1d').is(':checked')}}});
              return false;
            });
            $('form#A_W2').change(function(event) {
              socket.emit('data_send', {watering: {A: {W2: $('#A_W2d').is(':checked')}}});
              return false;
            });
            $('form#B_W1').change(function(event) {
              socket.emit('data_send', {watering: {B: {W1: $('#B_W1d').is(':checked')}}});
              return false;
            });
            $('form#B_W2').change(function(event) {
              socket.emit('data_send', {watering: {B: {W2: $('#B_W2d').is(':checked')}}});
              return false;
            });
            $('form#C_W1').change(function(event) {
              socket.emit('data_send', {watering: {C: {W1: $('#C_W1d').is(':checked')}}});
              return false;
            });
            $('form#C_W2').change(function(event) {
              socket.emit('data_send', {watering: {C: {W2: $('#C_W2d').is(':checked')}}});
              return false;
            });
            $('form#D_W1').change(function(event) {
              socket.emit('data_send', {watering: {D: {W1: $('#D_W1d').is(':checked')}}});
              return false;
            });
            $('form#D_W2').change(function(event) {
              socket.emit('data_send', {watering: {D: {W2: $('#D_W2d').is(':checked')}}});
              return false;
            });


            dialog_ventnord = $( "#dialog-confirm-ventnord" ).dialog({
              autoOpen: false,
              resizable: false,
              height: "auto",
              width: 400,
              modal: true,
              buttons: {
                Ja: function() {
                  $( this ).dialog( "close" );
                  socket.emit('data_send', {motornord: {confirm: 'confirmed'}});
                },
                Nej: function() {
                  $( this ).dialog( "close" );
                }
              }
            });

            dialog_ventsyd = $( "#dialog-confirm-ventsyd" ).dialog({
              autoOpen: false,
              resizable: false,
              height: "auto",
              width: 400,
              modal: true,
              buttons: {
                Ja: function() {
                  $( this ).dialog( "close" );
                  socket.emit('data_send', {motorsyd: {confirm: 'confirmed'}});
                },
                Nej: function() {
                  $( this ).dialog( "close" );
                }
              }
            });
          });


   $(function() {
    var curPage="status";
    $("#menu a").click(function() {
      $("#"+curPage).hide();
      curPage=$(this).data("page");
      $("#"+curPage).show();
    });
  });


     //   function updateRangeInput(elem) {
     //     document.getElementById('bajsmannen').innerHTML=elem.val; 
     //   }
     function updateTextInput(val) {
      document.getElementById('textInput').innerHTML=val; 
    }

    function updateTextInput2(val) {
      document.getElementById('textInput2').innerHTML=val; 
    }

    function updateTextInput3(val) {
      document.getElementById('textInput3').innerHTML=val; 
    }

    function updateTextInput4(val) {
      document.getElementById('textInput4').innerHTML=val; 
    }

    function updateTextInput5(val) {
      document.getElementById('textInput5').innerHTML=val; 
    }

        // Load the Visualization API and the piechart package.
        google.charts.load('visualization', '1', {'packages':['corechart']});

        // Set a callback to run when the Google Visualization API is loaded.
        google.charts.setOnLoadCallback(drawChart);

        function drawChart() {

//AJAX Call is compulsory !
var sw = $(window).width();
var jsonData = $.ajax({
  url: "logg",
  dataType:"json",
  async: false
}).responseText;

          // Create our data table out of JSON data loaded from server.
          var data = new google.visualization.DataTable(jsonData);

          
          var options = {
            hAxis: {
              title: 'Timme',
              format: 'd/M HH:mm'

            },
            vAxis: {
              title: 'Celcius'
            },
            chartArea: {
              width: sw
            }
          };
          // Instantiate and draw our chart, passing in some options.
          // Do not forget to check your div ID
          var chart = new google.visualization.LineChart(document.getElementById('logg'));
          chart.draw(data, options);

        }

        $(document).ready(function(){
          setTimeout(function() {
                    // First load the chart once 
                    drawChart();
                  }, 2000);
          $("#logg").hide();
                    // Set interval to call the drawChart again
                    setInterval(drawChart, 50000);
                  });