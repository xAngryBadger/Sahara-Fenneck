; Sahara Fennec Installer (Inno Setup)
#define MyAppName "Sahara Fennec"
#define MyAppVersion "2.0"
#define MyAppPublisher "Sahara Fennec"
#define MyAppExeName "FennecExcel.exe"

[Setup]
AppId={{A3B2E7A1-99DE-4ED2-8F11-FENNEC2026001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Sahara Fennec
DefaultGroupName=Sahara Fennec
DisableProgramGroupPage=no
OutputDir=..\build\installer
OutputBaseFilename=SaharaFennec-Setup-Legacy
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
SetupIconFile=..\assets\fennec_head_icon.ico
WizardImageFile=..\assets\installer_wizard.bmp
WizardSmallImageFile=..\assets\installer_small.bmp
; Desinstalador: criado automaticamente pelo Inno (menu Iniciar + Programas e Recursos)
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "runbootstrap"; Description: "Configurar Ollama e baixar modelos selecionados na próxima tela"; GroupDescription: "Pós-instalação:"; Flags: checkedonce

[Files]
Source: "..\dist\FennecExcel\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "bootstrap\postinstall.ps1"; DestDir: "{app}\bootstrap"; Flags: ignoreversion
; Música do instalador (extraída para {tmp}, reproduzida com opção de mutar)
Source: "sounds\installer_music.mp3"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{group}\Sahara Fennec"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Sahara Fennec"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Bootstrap (Ollama + modelos) é executado em [Code] CurStepChanged com os modelos escolhidos na página
Filename: "{app}\{#MyAppExeName}"; Description: "Executar Sahara Fennec"; Flags: nowait postinstall skipifsilent

[Code]
var
  MuteBtn: TNewButton;
  MusicMuted: Boolean;
  MciAlias: String;
  ModelsPage: TWizardPage;
  Chk14b, Chk7b, Chk3b, ChkPhi: TNewCheckBox;

function mciSendStringW(lpstrCommand: String; lpstrReturnString: String; uReturnLength: Cardinal; hWndCallback: Integer): Integer;
  external 'mciSendStringW@winmm.dll stdcall';

procedure StopMusic;
var
  Ret: Integer;
begin
  Ret := mciSendStringW('STOP ' + MciAlias, '', 0, 0);
  if Ret = 0 then
    mciSendStringW('CLOSE ' + MciAlias, '', 0, 0);
end;

procedure PlayMusic;
var
  Path: String;
  Cmd: String;
  Ret: Integer;
begin
  if not FileExists(ExpandConstant('{tmp}\installer_music.mp3')) then Exit;
  Path := ExpandConstant('{tmp}\installer_music.mp3');
  Cmd := 'OPEN "' + Path + '" TYPE MPEGVIDEO ALIAS ' + MciAlias;
  Ret := mciSendStringW(Cmd, '', 0, 0);
  if Ret = 0 then
    mciSendStringW('PLAY ' + MciAlias + ' REPEAT', '', 0, 0);
end;

procedure ToggleMute(Sender: TObject);
begin
    MusicMuted := not MusicMuted;
  if MusicMuted then
  begin
    StopMusic;
    MuteBtn.Caption := 'Ouvir música';
  end
  else
  begin
    PlayMusic;
    MuteBtn.Caption := 'Mutar música';
  end;
end;

function GetSelectedModelsParam: String;
var
  List: String;
begin
  List := '';
  if Chk7b.Checked then List := List + 'qwen2.5:7b,';
  if Chk14b.Checked then List := List + 'qwen2.5:14b,';
  if Chk3b.Checked then List := List + 'qwen2.5:3b,';
  if ChkPhi.Checked then List := List + 'phi3:mini,';
  if List <> '' then
    Result := Copy(List, 1, Length(List) - 1)
  else
    Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Params: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('runbootstrap') then
    begin
      Params := GetSelectedModelsParam;
      Exec('powershell.exe',
        '-ExecutionPolicy Bypass -File """' + ExpandConstant('{app}\bootstrap\postinstall.ps1') + '""" -WriteConfig:$true -ModelsToPull "' + Params + '"',
        '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure InitializeWizard;
var
  Path: String;
  Y: Integer;
begin
  MciAlias := 'FennecBGM';
  MusicMuted := False;
  ExtractTemporaryFile('installer_music.mp3');
  if FileExists(ExpandConstant('{tmp}\installer_music.mp3')) then
  begin
    PlayMusic;
    MuteBtn := TNewButton.Create(WizardForm);
    MuteBtn.Parent := WizardForm;
    MuteBtn.Caption := 'Mutar música';
    MuteBtn.Left := ScaleX(16);
    MuteBtn.Top := WizardForm.CancelButton.Top;
    MuteBtn.Width := ScaleX(90);
    MuteBtn.Height := WizardForm.CancelButton.Height;
    MuteBtn.OnClick := @ToggleMute;
  end;

  { Página "Modelos do assistente" — texto simples e didático }
  ModelsPage := CreateCustomPage(wpSelectTasks, 'Baixar modelos do assistente', 'O Fennec usa um modelo de linguagem para conversar com você. Marque abaixo os que deseja baixar agora (pode marcar mais de um). O instalador já vai escolher um recomendado para seu PC.');
  Y := 12;
  Chk7b := TNewCheckBox.Create(ModelsPage);
  Chk7b.Parent := ModelsPage.Surface;
  Chk7b.Left := 0;
  Chk7b.Top := Y;
  Chk7b.Width := ModelsPage.SurfaceWidth;
  Chk7b.Caption := 'qwen2.5:7b — Recomendado para a maioria dos PCs (bom equilíbrio)';
  Chk7b.Checked := True;
  Y := Y + 26;
  Chk14b := TNewCheckBox.Create(ModelsPage);
  Chk14b.Parent := ModelsPage.Surface;
  Chk14b.Left := 0;
  Chk14b.Top := Y;
  Chk14b.Width := ModelsPage.SurfaceWidth;
  Chk14b.Caption := 'qwen2.5:14b — Melhor qualidade, exige PC com mais RAM';
  Chk14b.Checked := False;
  Y := Y + 26;
  Chk3b := TNewCheckBox.Create(ModelsPage);
  Chk3b.Parent := ModelsPage.Surface;
  Chk3b.Left := 0;
  Chk3b.Top := Y;
  Chk3b.Width := ModelsPage.SurfaceWidth;
  Chk3b.Caption := 'qwen2.5:3b — Mais leve, ideal para PCs com pouca memória';
  Chk3b.Checked := False;
  Y := Y + 26;
  ChkPhi := TNewCheckBox.Create(ModelsPage);
  ChkPhi.Parent := ModelsPage.Surface;
  ChkPhi.Left := 0;
  ChkPhi.Top := Y;
  ChkPhi.Width := ModelsPage.SurfaceWidth;
  ChkPhi.Caption := 'phi3:mini — Alternativa leve e rápida';
  ChkPhi.Checked := False;
end;

procedure DeinitializeSetup;
begin
  StopMusic;
end;
