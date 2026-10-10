import gdrive_helper
service = gdrive_helper.get_drive_service()
res_f = service.files().list(q="'1S0qj0iU6f9QXkkJFLdX3Lqku6uFB_jXc' in parents and name = '01_Summary_Excel_Results' and trashed = false").execute().get('files', [])
print(res_f)
