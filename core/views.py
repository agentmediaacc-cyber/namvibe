from django.http import HttpResponse

def index(request):
    return HttpResponse("""
    <html>
      <head>
        <title>Namvibe</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: white;
            padding: 40px;
            text-align: center;
          }
          .box {
            max-width: 700px;
            margin: 60px auto;
            background: #111827;
            border-radius: 18px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,.35);
          }
          h1 { margin-bottom: 10px; }
          p { color: #cbd5e1; }
        </style>
      </head>
      <body>
        <div class="box">
          <h1>Namvibe is live 🚀</h1>
          <p>The app is running on Railway.</p>
          <p>Homepage template is being rebuilt safely.</p>
        </div>
      </body>
    </html>
    """)
