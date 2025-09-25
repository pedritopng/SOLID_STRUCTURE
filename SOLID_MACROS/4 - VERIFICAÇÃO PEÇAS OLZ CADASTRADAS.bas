' MACRO PARA VERIFICAR SE TODAS AS PEÇAS OLZ ESTÃO CADASTRADAS
' Compara peças OLZ da montagem com arquivo CSV de referência

Option Explicit

Const DELIM As String = ";"

Dim CODE_PROPS() As String, DESC_PROPS() As String
Dim gMissingDesc As Object, gNotRegistered As Object

Public Sub Main()
    Dim swApp As Object, swModel As Object
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Or swModel.GetType <> 2 Then
        MsgBox "Abra uma montagem antes de executar."
        Exit Sub
    End If
    
    InitPropNames
    
    Dim dict As Object: Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare
    
    Set gMissingDesc = CreateObject("Scripting.Dictionary"): gMissingDesc.CompareMode = vbTextCompare
    Set gNotRegistered = CreateObject("Scripting.Dictionary"): gNotRegistered.CompareMode = vbTextCompare
    
    Dim cfg As Object, root As Object
    Set cfg = swModel.GetActiveConfiguration
    Set root = cfg.GetRootComponent3(True)
    If root Is Nothing Then
        MsgBox "Montagem sem componente raiz válido."
        Exit Sub
    End If
    
    TraverseComponent root, dict, True
    
    Debug.Print "=== RESULTADO DA BUSCA ==="
    Debug.Print "Total de peças OLZ encontradas: " & dict.Count
    
    ' Removido: verificação de descrição vazia (não é mais necessária)
    
    If dict.Count = 0 Then
        MsgBox "Nenhuma peça OLZ foi encontrada na montagem.", vbInformation
        Exit Sub
    End If
    
    ' Verificar se todas as peças OLZ estão cadastradas
    CheckRegistrationStatus dict
    
    ' Mostrar relatório final
    ShowFinalReport dict
End Sub

Private Sub InitPropNames()
    CODE_PROPS = Split("CODE;CODIGO;COD;PART_NO;PART_NUMBER;NUMERO_PECA;NUMERO", ";")
    DESC_PROPS = Split("DESCRIPTION;DESCRICAO;DESC;NOME;NAME", ";")
End Sub

Private Sub TraverseComponent(comp As Object, dict As Object, isRoot As Boolean)
    If comp Is Nothing Then Exit Sub
    If IsSuppressedSafe(comp) Then Exit Sub
    
    Dim md As Object: Set md = comp.GetModelDoc2
    If md Is Nothing Then Exit Sub
    
    Dim cfg As Object: Set cfg = GetConfigurationSafe(comp)
    Dim cfgName As String
    If cfg Is Nothing Then
        cfgName = "Default"
    Else
        cfgName = cfg.Name
    End If
    
    ' Verificar se é peça OLZ
    Dim fullPath As String: fullPath = md.GetPathName
    Dim fileName As String: fileName = BaseName(fullPath)
    
    If IsOLZPart(fileName) Then
        Debug.Print "=== PROCESSANDO OLZ ==="
        Debug.Print "Arquivo: " & fileName
        
        ' Debug especial para peças Z03
        If Left$(fileName, 3) = "Z03" Then
            Debug.Print "*** PEÇA Z03 DETECTADA: " & fileName & " ***"
        ElseIf Left$(fileName, 3) = "OLZ" Then
            Debug.Print "*** PEÇA OLZ DETECTADA: " & fileName & " ***"
        End If
        
        ' Se é OLZ, processar TODAS as configurações (não apenas a ativa)
        Dim configNames As Variant
        On Error Resume Next
        configNames = md.GetConfigurationNames
        On Error GoTo 0
        
        Debug.Print "ConfigNames é array? " & IsArray(configNames)
        If IsArray(configNames) Then
            Debug.Print "Total de configurações: " & (UBound(configNames) - LBound(configNames) + 1)
            Debug.Print "LBound: " & LBound(configNames) & ", UBound: " & UBound(configNames)
            
            ' Debug: mostrar todas as configurações encontradas
            Dim debugK As Long
            For debugK = LBound(configNames) To UBound(configNames)
                Debug.Print "  Config[" & debugK & "]: " & configNames(debugK)
            Next debugK
            Dim k As Long
            For k = LBound(configNames) To UBound(configNames)
                Debug.Print "  Loop k = " & k
                On Error Resume Next
                Dim currentConfigName As String: currentConfigName = configNames(k)
                If Err.Number <> 0 Then
                    Debug.Print "    ERRO ao obter configNames(" & k & "): " & Err.Description
                    Err.Clear
                    GoTo NextConfig
                End If
                On Error GoTo 0
                
                Debug.Print "  currentConfigName: " & currentConfigName
                Dim currentCfg As Object: Set currentCfg = GetConfigurationByNameSafe(md, currentConfigName)
                If currentCfg Is Nothing Then 
                    Debug.Print "  currentCfg é Nothing para: " & currentConfigName
                    GoTo NextConfig
                End If
                
                ' Processar esta configuração
                Debug.Print "  Processando config: " & currentConfigName
                ProcessOLZConfiguration currentCfg, md, currentConfigName, fullPath, fileName, dict
NextConfig:
            Next k
            Debug.Print "  Fim do loop de configurações"
        Else
            ' Fallback: se não conseguiu obter configurações, processar apenas a ativa
            Debug.Print "Fallback: processando configuração ativa"
            Debug.Print "cfgName: " & cfgName
            ProcessOLZConfiguration cfg, md, cfgName, fullPath, fileName, dict
        End If
    End If
    
    ' SEMPRE continuar recursão para processar submontagens
    Dim children As Variant: children = comp.GetChildren
    If IsArray(children) Then
        Dim j As Long
        For j = LBound(children) To UBound(children)
            Dim childComp As Object: Set childComp = children(j)
            TraverseComponent childComp, dict, False
        Next j
    End If
End Sub

Private Function IsOLZPart(ByVal baseName As String) As Boolean
    ' Verifica se o nome do arquivo começa com "OLZ"
    ' Verificar tanto OLZ quanto Z03 (peças que podem ter códigos específicos)
    Dim prefix As String: prefix = UCase$(Left$(baseName, 3))
    IsOLZPart = (prefix = "OLZ" Or prefix = "Z03")
End Function

Private Function CleanCode(ByVal s As String) As String
    Dim temp As String: temp = Replace(s, " ", "")
    temp = Replace(temp, "-", "")
    Dim upperTemp As String: upperTemp = UCase$(temp)
    If Not (Right$(upperTemp, 1) = "M" Or Right$(upperTemp, 2) = "E1" Or Right$(upperTemp, 2) = "E2") Then
        temp = Replace(temp, "OL", "", 1, -1, vbTextCompare)
    End If
    CleanCode = temp
End Function

Private Function GetFirstProp(md As Object, cfgName As String, propNames() As String) As String
    On Error Resume Next
    Dim i As Long
    For i = LBound(propNames) To UBound(propNames)
        Dim val As String: val = md.GetCustomPropertyValue2(propNames(i), cfgName)
        If Len(Trim$(val)) > 0 Then GetFirstProp = val: Exit Function
    Next i
    On Error GoTo 0
End Function

Private Function BaseName(ByVal fullPath As String) As String
    Dim pos As Long: pos = InStrRev(fullPath, "\")
    If pos > 0 Then
        Dim withoutExt As String: withoutExt = Left$(fullPath, InStrRev(fullPath, ".") - 1)
        BaseName = Mid$(withoutExt, pos + 1)
    Else
        BaseName = fullPath
    End If
    ' Debug.Print "BaseName resultado: '" & BaseName & "'"
End Function

Private Sub CheckRegistrationStatus(ByRef dict As Object)
    Dim csvPath As String: csvPath = "P:\GUINCHOS E GUINDASTES\OL1 - GERENCIAMENTO DE PROJETO\TODOS CADASTRADOS.csv"
    
    ' Verificar se arquivo existe
    If Dir(csvPath) = "" Then
        MsgBox "Arquivo de referência não encontrado: " & vbCrLf & csvPath, vbCritical, "Erro"
        Exit Sub
    End If
    
    ' Ler arquivo CSV e criar dicionário de códigos cadastrados
    Dim registeredCodes As Object: Set registeredCodes = CreateObject("Scripting.Dictionary")
    registeredCodes.CompareMode = vbTextCompare
    
    Dim f As Integer: f = FreeFile
    Open csvPath For Input As #f
    
    Dim line As String
    Do While Not EOF(f)
        Line Input #f, line
        If Len(Trim$(line)) > 0 Then
            ' Extrair primeira coluna (código)
            Dim code As String: code = ExtractFirstColumn(line)
            If Len(Trim$(code)) > 0 Then
                ' Ignorar códigos que contenham "^"
                If InStr(code, "^") = 0 Then
                    If Not registeredCodes.Exists(code) Then
                        registeredCodes.Add code, ""
                    End If
                End If
            End If
        End If
    Loop
    Close #f
    
    ' Comparar códigos da montagem com códigos cadastrados
    Dim k As Variant
    For Each k In dict.Keys
        ' Extrair apenas o código limpo (antes do primeiro "|") para comparação
        Dim codeToCheck As String: codeToCheck = CStr(k)
        Dim pipePos As Long: pipePos = InStr(codeToCheck, "|")
        If pipePos > 0 Then codeToCheck = Left$(codeToCheck, pipePos - 1)
        
        If Not registeredCodes.Exists(codeToCheck) Then
            If Not gNotRegistered.Exists(k) Then
                gNotRegistered.Add k, dict(k)
            End If
        End If
    Next k
End Sub

Private Function ExtractFirstColumn(ByVal line As String) As String
    Dim pos As Long: pos = InStr(line, DELIM)
    If pos > 0 Then
        ExtractFirstColumn = Left$(line, pos - 1)
    Else
        ExtractFirstColumn = line
    End If
    ' Remover aspas se existirem
    ExtractFirstColumn = Replace(ExtractFirstColumn, """", "")
End Function

Private Sub ReportMissingDescriptions(ByVal missing As Object)
    Dim msg As String, k As Variant, n As Long
    msg = "ERRO: Os seguintes códigos OLZ estão com a descrição vazia (" & CStr(missing.Count) & "):" & vbCrLf & vbCrLf
    For Each k In missing.Keys
        n = n + 1
        msg = msg & n & ". " & k & vbCrLf
        If n >= 10 Then
            msg = msg & "... e mais " & (missing.Count - 10) & " itens." & vbCrLf
            Exit For
        End If
    Next k
    MsgBox msg, vbCritical, "Descrições Vazias"
End Sub

Private Sub ShowFinalReport(ByRef dict As Object)
    Dim totalOLZ As Long: totalOLZ = dict.Count
    Dim notRegistered As Long: notRegistered = gNotRegistered.Count
    Dim registered As Long: registered = totalOLZ - notRegistered
    
    Dim msg As String
    msg = "RELATÓRIO DE VERIFICAÇÃO DE PEÇAS OLZ CADASTRADAS" & vbCrLf & vbCrLf
    msg = msg & "Total de peças OLZ na montagem: " & totalOLZ & vbCrLf
    msg = msg & "Peças já cadastradas: " & registered & vbCrLf
    msg = msg & "Peças NÃO cadastradas: " & notRegistered & vbCrLf & vbCrLf
    
    If notRegistered > 0 Then
        msg = msg & "PEÇAS QUE PRECISAM SER CADASTRADAS:" & vbCrLf & vbCrLf
        Dim k As Variant, n As Long: n = 0
        For Each k In gNotRegistered.Keys
            n = n + 1
            ' Extrair apenas o código limpo para exibição
            Dim displayCode As String: displayCode = CStr(k)
            Dim displayPipePos As Long: displayPipePos = InStr(displayCode, "|")
            If displayPipePos > 0 Then displayCode = Left$(displayCode, displayPipePos - 1)
            
            msg = msg & n & ". " & displayCode & " - " & gNotRegistered(k) & vbCrLf
            If n >= 20 Then
                msg = msg & "... e mais " & (notRegistered - 20) & " itens." & vbCrLf
                Exit For
            End If
        Next k
        
        msg = msg & vbCrLf & "AÇÃO NECESSÁRIA: Cadastrar as peças listadas acima no sistema."
        MsgBox msg, vbExclamation, "Peças Não Cadastradas Encontradas"
    Else
        msg = msg & "? TODAS AS PEÇAS OLZ JÁ ESTÃO CADASTRADAS!"
        MsgBox msg, vbInformation, "Verificação Concluída"
    End If
End Sub

Private Function IsSuppressedSafe(comp As Object) As Boolean
    On Error Resume Next
    IsSuppressedSafe = comp.IsSuppressed
    On Error GoTo 0
End Function

Private Function GetConfigurationSafe(comp As Object) As Object
    On Error Resume Next
    Set GetConfigurationSafe = comp.GetConfiguration
    On Error GoTo 0
End Function

Private Function GetConfigurationByNameSafe(md As Object, configName As String) As Object
    On Error Resume Next
    
    ' Se for "Valor predeterminado" ou "Default", usar GetActiveConfiguration
    If configName = "Valor predeterminado" Or configName = "Default" Then
        Set GetConfigurationByNameSafe = md.GetActiveConfiguration
    Else
        ' Para outras configurações, tentar diferentes métodos
        Dim configMgr As Object
        Set configMgr = md.GetConfigurationManager
        If Not configMgr Is Nothing Then
            ' Tentar GetConfigurationByName primeiro
            Set GetConfigurationByNameSafe = configMgr.GetConfigurationByName(configName)
            
            ' Se falhou, tentar obter por índice
            If GetConfigurationByNameSafe Is Nothing Then
                Debug.Print "    Tentando obter por índice para: " & configName
                Dim configNames As Variant
                configNames = md.GetConfigurationNames
                If IsArray(configNames) Then
                    Dim i As Long
                    For i = LBound(configNames) To UBound(configNames)
                        If configNames(i) = configName Then
                            Set GetConfigurationByNameSafe = configMgr.GetConfigurationByIndex(i)
                            Debug.Print "    Obtido por índice " & i & ": " & (Not GetConfigurationByNameSafe Is Nothing)
                            Exit For
                        End If
                    Next i
                End If
            Else
                Debug.Print "    Obtido por nome: " & configName
            End If
        End If
    End If
    
    If Err.Number <> 0 Then
        Debug.Print "    ERRO GetConfigurationByNameSafe: " & Err.Description & " para " & configName
        Err.Clear
        Set GetConfigurationByNameSafe = Nothing
    End If
    On Error GoTo 0
End Function

Private Function GetConfigurationPartNumber(cfg As Object, md As Object) As String
    On Error Resume Next
    If cfg Is Nothing Then Exit Function

    ' 1) Tentar cfg.GetPartNumber (método direto)
    Dim partNumber As String: partNumber = cfg.GetPartNumber
    If Len(Trim$(partNumber)) > 0 Then GetConfigurationPartNumber = partNumber: Exit Function

    ' 2) Tentar propriedades customizadas com nomes específicos
    Dim partNumberProps() As String
    partNumberProps = Split("Part Number;PartNumber;Part_Number;Número de peça;Numero de peça;Número;Number;Part No;PartNo", ";")
    
    Dim i As Long
    For i = LBound(partNumberProps) To UBound(partNumberProps)
        partNumber = md.GetCustomPropertyValue2(partNumberProps(i), cfg.Name)
        If Len(Trim$(partNumber)) > 0 Then GetConfigurationPartNumber = partNumber: Exit Function
    Next i

    ' 3) Tentar propriedades do documento (sem configuração específica)
    For i = LBound(partNumberProps) To UBound(partNumberProps)
        partNumber = md.GetCustomPropertyValue2(partNumberProps(i), "")
        If Len(Trim$(partNumber)) > 0 Then GetConfigurationPartNumber = partNumber: Exit Function
    Next i

    On Error GoTo 0
End Function

Private Function GetBOMPartNumber(cfg As Object, md As Object) As String
    On Error Resume Next
    If cfg Is Nothing Then Exit Function
    
    ' Tentar cfg.GetBOMPartNumber primeiro
    Dim bomPartNumber As String: bomPartNumber = cfg.GetBOMPartNumber
    If Len(Trim$(bomPartNumber)) > 0 Then GetBOMPartNumber = bomPartNumber: Exit Function
    
    ' Se não funcionou, tentar obter via propriedades customizadas
    Dim bomProps() As String
    bomProps = Split("BOMPartNumber;BOM_Part_Number;BOMPartNo;BOMPart_No;BOMPart", ";")
    
    Dim i As Long
    For i = LBound(bomProps) To UBound(bomProps)
        bomPartNumber = md.GetCustomPropertyValue2(bomProps(i), cfg.Name)
        If Len(Trim$(bomPartNumber)) > 0 Then GetBOMPartNumber = bomPartNumber: Exit Function
    Next i
    
    ' Tentar sem configuração específica
    For i = LBound(bomProps) To UBound(bomProps)
        bomPartNumber = md.GetCustomPropertyValue2(bomProps(i), "")
        If Len(Trim$(bomPartNumber)) > 0 Then GetBOMPartNumber = bomPartNumber: Exit Function
    Next i
    
    On Error GoTo 0
End Function

Private Sub ProcessOLZConfiguration(cfg As Object, md As Object, configName As String, fullPath As String, fileName As String, dict As Object)
    ' Processar código para esta configuração específica
    Dim codeRaw As String: codeRaw = GetConfigurationPartNumber(cfg, md)
    Dim isFromPartNumber As Boolean: isFromPartNumber = (Len(Trim$(codeRaw)) > 0)
    
    Debug.Print "    codeRaw (PartNumber): " & codeRaw
    
    ' Se não conseguiu pelo Part Number, tentar GetBOMPartNumber
    If Not isFromPartNumber Then
        codeRaw = GetBOMPartNumber(cfg, md)
        isFromPartNumber = (Len(Trim$(codeRaw)) > 0)
        Debug.Print "    codeRaw (BOM): " & codeRaw
    End If
    
    If Not isFromPartNumber Then 
        codeRaw = GetFirstProp(md, configName, CODE_PROPS)
        Debug.Print "    codeRaw (Props): " & codeRaw
    End If
    If Len(Trim$(codeRaw)) = 0 Then codeRaw = fileName
    Debug.Print "    codeRaw final: " & codeRaw
    
    Dim codeClean As String
    If isFromPartNumber Then
        ' Se veio do Part Number, usar sem limpeza (manter formato original)
        codeClean = codeRaw
    Else
        ' Se veio de outras fontes, aplicar limpeza
        codeClean = CleanCode(codeRaw)
    End If
    
    Debug.Print "    codeClean final: " & codeClean
    
    ' Debug para parafusos Z03
    If Left$(codeClean, 3) = "Z03" Then
        Debug.Print "=== PARAFUSO Z03 ==="
        Debug.Print "Configuração: " & configName
        Debug.Print "Código obtido: " & codeClean
        Debug.Print "Arquivo: " & fileName
        Debug.Print "==================="
    End If
    
    ' Ignorar códigos que contenham "^"
    If InStr(codeClean, "^") = 0 Then
        ' Gerar chave única incluindo configuração e caminho
        Dim uniqueKey As String: uniqueKey = codeClean & "|" & configName & "|" & fullPath
        
        Debug.Print "    uniqueKey: " & uniqueKey
        
        ' Adicionar ao dicionário se não existir
        If Not dict.Exists(uniqueKey) Then
            dict.Add uniqueKey, codeClean
            Debug.Print "    ADICIONADO ao dicionário!"
        Else
            Debug.Print "    JÁ EXISTE no dicionário"
        End If
    Else
        Debug.Print "    IGNORADO por conter '^'"
    End If
End Sub
