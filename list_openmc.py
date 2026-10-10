import gdrive_helper
service = gdrive_helper.get_drive_service()
res = service.files().list(q="'1S0qj0iU6f9QXkkJFLdX3Lqku6uFB_jXc' in parents", fields="files(id, name, mimeType)").execute().get('files', [])
print(res)
