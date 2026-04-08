; ============================================================================
; Sahara Fennec - Instalador Slim
; Instala TUDO: Miniconda, ambiente Python, dependencias, Ollama, modelo IA.
; Usuario so clica Avancar.
; ============================================================================
#define MyAppName "Sahara Fennec"
#define MyAppVersion "2.0"
#define MyAppPublisher "Sahara Fennec"

[Setup]
AppId={{B4C3F8B2-88EF-4ED3-9E22-FENNEC2026002}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppMutex=SaharaFennecSetupMutex
DefaultDirName={autopf}\Sahara Fennec
DefaultGroupName=Sahara Fennec
DisableProgramGroupPage=no
OutputDir=..\build\installer
OutputBaseFilename=SaharaFennec-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
PrivilegesRequired=admin
MinVersion=10.0
SetupIconFile=..\assets\fennec_head_icon.ico
WizardImageFile=..\assets\installer_wizard.bmp
WizardSmallImageFile=..\assets\installer_small.bmp
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\assets\fennec_head_icon.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\main.py"; DestDir: "{app}"
Source: "..\src\*"; DestDir: "{app}\src"; Flags: recursesubdirs createallsubdirs
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs
Source: "..\requirements-slim.txt"; DestDir: "{app}"
Source: "run_fennec.bat"; DestDir: "{app}"
Source: "configurar_ambiente.bat"; DestDir: "{app}"
Source: "bootstrap\postinstall.ps1"; DestDir: "{app}\bootstrap"; Flags: ignoreversion
Source: "bootstrap\setup_slim.ps1"; DestDir: "{app}\bootstrap"; Flags: ignoreversion

[Icons]
Name: "{group}\Sahara Fennec"; Filename: "{app}\run_fennec.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Sahara Fennec"; Filename: "{app}\run_fennec.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\run_fennec.bat"; Description: "Executar Sahara Fennec"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}"

[UninstallRun]
Filename: "cmd.exe"; Parameters: "/c rd /s /q ""%TEMP%\SaharaFennec"" 2>nul"; Flags: runhidden waituntilterminated; RunOnceId: "CleanTemp"

[Code]
var
  ModelsPage: TWizardPage;
  Chk14b, Chk7b, Chk3b, ChkPhi: TNewCheckBox;
  ProgressPage: TOutputProgressWizardPage;

{ ---- File-based IPC paths ---- }
function GetStatusFilePath: String;
begin
  Result := ExpandConstant('{userappdata}\SaharaFennec\bootstrap_status.txt');
end;

function GetDoneFilePath: String;
begin
  Result := ExpandConstant('{userappdata}\SaharaFennec\bootstrap_done.txt');
end;

{ ---- Build the powershell command line ---- }
function BuildCmdLine(const AppDir, Models: String): String;
var
  PS1: String;
begin
  PS1 := AppDir + '\bootstrap\setup_slim.ps1';
  Result := '/c powershell.exe -ExecutionPolicy Bypass -NoProfile -File "' + PS1 + '"' +
            ' -AppDir "' + AppDir + '"' +
            ' -ModelsToPull "' + Models + '"' +
            ' -RunBootstrap' +
            ' -StatusFile "' + GetStatusFilePath + '"' +
            ' -DoneFile "' + GetDoneFilePath + '"';
end;

{ ---- Main bootstrap runner ---- }
function RunBootstrapWithProgress(const AppDir, Models: String): Boolean;
var
  RC: Integer;
  CmdArgs: String;
  StatusPath, DonePath: String;
  StatusBuf, DoneBuf: AnsiString;
  LastStatus: AnsiString;
  Loops, MaxLoops, Pct: Integer;
begin
  Result := False;
  MaxLoops := 21600; { 3h at 500ms = 21600 loops }

  StatusPath := GetStatusFilePath;
  DonePath := GetDoneFilePath;

  { Clean previous run files }
  DeleteFile(StatusPath);
  DeleteFile(DonePath);

  { Ensure target directory exists }
  ForceDirectories(ExpandConstant('{userappdata}\SaharaFennec'));

  CmdArgs := BuildCmdLine(AppDir, Models);

  ProgressPage.SetText('Configurando Sahara Fennec...', 'Iniciando...');
  ProgressPage.SetProgress(0, 100);
  ProgressPage.Show;

  { Launch via cmd.exe — most reliable way on all Windows }
  if not Exec(ExpandConstant('{cmd}'), CmdArgs, AppDir, SW_HIDE, ewNoWait, RC) then
  begin
    ProgressPage.Hide;
    MsgBox('Falha ao iniciar configurador.' + #13#10 +
           'Tente executar o instalador como Administrador.', mbError, MB_OK);
    Exit;
  end;

  Loops := 0;
  LastStatus := '';

  while Loops < MaxLoops do
  begin
    Loops := Loops + 1;

    { ---- Check if done ---- }
    if LoadStringFromFile(DonePath, DoneBuf) then
    begin
      DoneBuf := Trim(DoneBuf);
      if DoneBuf <> '' then
      begin
        { Done! Check result }
        if Pos('OK', DoneBuf) = 1 then
        begin
          ProgressPage.SetProgress(100, 100);
          ProgressPage.SetText('Configurando Sahara Fennec...', 'Concluido!');
          Sleep(400);
          ProgressPage.Hide;
          Result := True;
          Exit;
        end
        else
        begin
          ProgressPage.Hide;
          MsgBox('Falha na configuracao:' + #13#10 +
                 Copy(DoneBuf, 7, Length(DoneBuf)) + #13#10#13#10 +
                 'Veja o log em:' + #13#10 +
                 '%APPDATA%\SaharaFennec\bootstrap.log', mbError, MB_OK);
          Exit;
        end;
      end;
    end;

    { ---- Read status updates ---- }
    if LoadStringFromFile(StatusPath, StatusBuf) then
    begin
      StatusBuf := Trim(StatusBuf);
      if (StatusBuf <> '') and (StatusBuf <> LastStatus) then
      begin
        ProgressPage.SetText('Configurando Sahara Fennec...', StatusBuf);
        LastStatus := StatusBuf;
      end;
    end;

    { ---- Progress bar: slow crawl from 2% to 95% ---- }
    Pct := 2 + ((Loops * 93) div MaxLoops);
    if Pct > 95 then Pct := 95;
    ProgressPage.SetProgress(Pct, 100);

    { ---- Early crash detection: 180s no files = likely dead process ---- }
    if (Loops = 360) then
    begin
      if (not FileExists(StatusPath)) and (not FileExists(DonePath)) then
      begin
        ProgressPage.Hide;
        MsgBox('O configurador nao respondeu nos primeiros 3 minutos.' + #13#10 +
               'Verifique o log em:' + #13#10 +
               '%APPDATA%\SaharaFennec\bootstrap.log', mbError, MB_OK);
        Exit;
      end;
    end;

    Sleep(500);
    WizardForm.Refresh;
  end;

  { Timeout reached }
  ProgressPage.Hide;
  MsgBox('A configuracao demorou alem do limite (3h).' + #13#10 +
         'Verifique o log em %APPDATA%\SaharaFennec\bootstrap.log.', mbError, MB_OK);
end;

{ ---- Collect selected models ---- }
function GetSelectedModels: String;
var
  S: String;
begin
  S := '';
  if Chk7b.Checked then S := S + 'qwen2.5:7b,';
  if Chk14b.Checked then S := S + 'qwen2.5:14b,';
  if Chk3b.Checked then S := S + 'qwen2.5:3b,';
  if ChkPhi.Checked then S := S + 'phi3:mini,';
  if S <> '' then
    Result := Copy(S, 1, Length(S) - 1)
  else
    Result := '';
end;

{ ---- Post-install: run bootstrap ---- }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RunBootstrapWithProgress(ExpandConstant('{app}'), GetSelectedModels);
  end;
end;

{ ---- Wizard: model selection page ---- }
procedure InitializeWizard;
var
  Y: Integer;
  Lbl: TNewStaticText;
begin
  ProgressPage := CreateOutputProgressPage('Configurando Sahara Fennec', 'Preparando...');

  ModelsPage := CreateCustomPage(wpSelectTasks,
    'Modelos adicionais de IA',
    'O Fennec escolhe automaticamente o melhor modelo para este PC. Aqui voce decide apenas se deseja baixar modelos extras durante a instalacao.');

  Y := 8;
  Lbl := TNewStaticText.Create(ModelsPage);
  Lbl.Parent := ModelsPage.Surface;
  Lbl.Left := 0;
  Lbl.Top := Y;
  Lbl.Width := ModelsPage.SurfaceWidth;
  Lbl.Caption := 'Se nada for marcado, o instalador baixara automaticamente apenas o modelo recomendado para este hardware.';
  Lbl.Font.Style := [fsBold];
  Y := Y + 28;

  Chk7b := TNewCheckBox.Create(ModelsPage);
  Chk7b.Parent := ModelsPage.Surface;
  Chk7b.Left := 0;
  Chk7b.Top := Y;
  Chk7b.Width := ModelsPage.SurfaceWidth;
  Chk7b.Caption := 'qwen2.5:7b  -  Equilibrio entre velocidade e qualidade';
  Chk7b.Checked := False;
  Y := Y + 28;

  Chk3b := TNewCheckBox.Create(ModelsPage);
  Chk3b.Parent := ModelsPage.Surface;
  Chk3b.Left := 0;
  Chk3b.Top := Y;
  Chk3b.Width := ModelsPage.SurfaceWidth;
  Chk3b.Caption := 'qwen2.5:3b  -  Mais leve, ideal para PCs com pouca memoria';
  Chk3b.Checked := False;
  Y := Y + 28;

  Chk14b := TNewCheckBox.Create(ModelsPage);
  Chk14b.Parent := ModelsPage.Surface;
  Chk14b.Left := 0;
  Chk14b.Top := Y;
  Chk14b.Width := ModelsPage.SurfaceWidth;
  Chk14b.Caption := 'qwen2.5:14b  -  Melhor qualidade, exige hardware mais forte';
  Chk14b.Checked := False;
  Y := Y + 28;

  ChkPhi := TNewCheckBox.Create(ModelsPage);
  ChkPhi.Parent := ModelsPage.Surface;
  ChkPhi.Left := 0;
  ChkPhi.Top := Y;
  ChkPhi.Width := ModelsPage.SurfaceWidth;
  ChkPhi.Caption := 'phi3:mini  -  Alternativa leve e rapida';
  ChkPhi.Checked := False;
end;
