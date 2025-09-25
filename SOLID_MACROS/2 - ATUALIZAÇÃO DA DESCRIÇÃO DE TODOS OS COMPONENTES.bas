' MACRO PARA ATUALIZAR DESCRI��ES

' Coluna A: Codigo (sem "OL", "-" e " "
' Coluna B: Descricao da pe�a

' Verifica��o:
' Detec��o de c�digo de equipamento final mantendo OL
' Exclui linhas cujo CODIGO contenha "^"
' Inclui pe�as fabricadas e submontagens
' Verifica se tem alguma descri��o vazia e avisa quais s�o
' Verifica se alguma descri��o ultrapassou o limite de caracteres
' N�O inclui duplicatas
' N�O Inclui pe�as OLZ

' Vai no Importador com o c�digo 7


Option Explicit
' ======= OPCOES =======
Const MAX_DESC_WIDTH As Long = 80                ' Limite de LARGURA APROXIMADA para a descri��o
Const DELIM As String = ";"                      ' Delimitador CSV
' Propriedades candidatas
Dim CODE_PROPS() As String
Dim DESC_PROPS() As String
' Coletores globais
Dim gMissingDesc As Object                       ' Dicion�rio para descri��es vazias
Dim gLongDesc As Object                          ' Dicion�rio para descri��es longas (em largura)

Private Sub InitPropNames()
    CODE_PROPS = Split("C�digo;Codigo;Part Number;N�mero;Number", ";")
    DESC_PROPS = Split("Descri��o;Description;Descritivo;Desc", ";")
End Sub

Public Sub Main()
    Dim swApp As Object, swModel As Object
    Set swApp = Application.SldWorks
    Set swModel = swApp.ActiveDoc
    If swModel Is Nothing Or swModel.GetType <> 2 Then
        MsgBox "Abra uma montagem antes de executar."
        Exit Sub
    End If
    
    Call InitPropNames
    
    Dim dict As Object: Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare
    
    Set gMissingDesc = CreateObject("Scripting.Dictionary")
    gMissingDesc.CompareMode = vbTextCompare
    Set gLongDesc = CreateObject("Scripting.Dictionary")
    gLongDesc.CompareMode = vbTextCompare
    
    Dim swConf As Object, root As Object
    Set swConf = swModel.GetActiveConfiguration
    Set root = swConf.GetRootComponent3(True)
    If root Is Nothing Then
        MsgBox "Montagem sem componente raiz v�lido."
        Exit Sub
    End If
    TraverseComponent root, dict, True
    
    ' Valida��o cr�tica: Descri��o vazia
    If gMissingDesc.Count > 0 Then
        ReportMissingDescriptions gMissingDesc
        MsgBox "O processo foi interrompido. Corrija os itens com descri��o vazia antes de continuar.", vbCritical, "Gera��o de Arquivo Cancelada"
        Exit Sub
    End If
    
    ' Aviso: Descri��o longa
    If gLongDesc.Count > 0 Then
        ReportLongDescriptions gLongDesc
    End If
    
    ' Verifica��o: Letra F nos c�digos
    CheckForLetterF dict
    
    If dict.Count = 0 Then
        MsgBox "Nenhuma pe�a ou submontagem com descri��o v�lida foi encontrada para gerar o arquivo.", vbInformation
        Exit Sub
    End If
    
    Dim asmCodeRaw As String
    asmCodeRaw = GetBOMPartNumber(swModel.GetActiveConfiguration, swModel)
    If Len(Trim$(asmCodeRaw)) = 0 Then asmCodeRaw = GetFirstProp(swModel, swConf.Name, CODE_PROPS)
    If Len(Trim$(asmCodeRaw)) = 0 Then asmCodeRaw = BaseName(swModel.GetPathName)
    
    Dim safeCode As String: safeCode = SanitizeName(asmCodeRaw)
    Dim fileName As String: fileName = "ATUALIZAR DESCRI��O " & safeCode & ".csv"
    Dim outPath As String: outPath = BuildDesktopCadastroEquipCsvPath(safeCode, fileName)
    
    WriteCsv outPath, dict
    MsgBox "CSV gerado com sucesso: " & outPath
End Sub

Private Sub TraverseComponent(ByVal comp As Object, ByRef dict As Object, ByVal isRoot As Boolean)
    If comp Is Nothing Or IsSuppressedSafe(comp) Then Exit Sub
    
    If Not isRoot Then
        Dim md As Object: Set md = comp.GetModelDoc2
        If Not md Is Nothing Then
            Dim t As Long: t = md.GetType
            If t = 1 Or t = 2 Then
                Dim cfgName As String: cfgName = comp.ReferencedConfiguration
                Dim cfg As Object: Set cfg = md.GetConfigurationByName(cfgName)
                
                Dim codeRaw As String, descRaw As String
                
                ' Busca especificamente o Part Number da configura��o
                codeRaw = GetConfigurationPartNumber(cfg, md)
                
                ' Fallback para outras propriedades se Part Number n�o existir
                If Len(Trim$(codeRaw)) = 0 Then codeRaw = GetBOMPartNumber(cfg, md)
                If Len(Trim$(codeRaw)) = 0 Then codeRaw = GetFirstProp(md, cfgName, CODE_PROPS)
                If Len(Trim$(codeRaw)) = 0 Then codeRaw = BaseName(md.GetPathName)
                descRaw = GetFirstProp(md, cfgName, DESC_PROPS)
                
                Dim codeClean As String: codeClean = CleanCode(codeRaw)
                
                ' Debug: Mostrar informa��es sobre o que est� sendo processado
                Debug.Print "=== PROCESSANDO COMPONENTE ==="
                Debug.Print "Arquivo: " & md.GetPathName
                Debug.Print "Config: " & cfgName & " | PartNumber: " & codeRaw & " | CleanCode: " & codeClean
                Debug.Print "  -> GetBOMPartNumber: " & GetBOMPartNumber(cfg, md)
                Debug.Print "  -> BaseName: " & BaseName(md.GetPathName)
                
                ' Verificar se o componente est� marcado para ser exclu�do da lista de materiais
                Dim excludeFromBOM As Boolean: excludeFromBOM = IsExcludedFromBOM(comp, cfg)
                Debug.Print "  -> Exclu�do do BOM: " & excludeFromBOM
                
                If InStr(1, codeClean, "^", vbTextCompare) = 0 And Not excludeFromBOM Then
                    If Len(Trim$(descRaw)) = 0 Then
                        Dim uniqueKeyMissing As String: uniqueKeyMissing = codeClean & "|" & cfgName & "|" & md.GetPathName
                        If Not gMissingDesc.Exists(uniqueKeyMissing) Then gMissingDesc.Add uniqueKeyMissing, ""
                    Else
                        ' Se a descri��o n�o estiver vazia, adiciona ao dicion�rio (mesmo se for longa)
                        ' Usa o c�digo limpo + configura��o + caminho do arquivo para garantir unicidade absoluta
                        Dim uniqueKey As String: uniqueKey = codeClean & "|" & cfgName & "|" & md.GetPathName
                        Debug.Print "    -> UniqueKey: " & uniqueKey
                        Debug.Print "    -> J� existe no dict: " & dict.Exists(uniqueKey)
                        If Not dict.Exists(uniqueKey) Then
                            dict.Add uniqueKey, descRaw
                            Debug.Print "    -> ADICIONADO ao dict"
                        Else
                            Debug.Print "    -> PULADO (j� existe)"
                        End If
                        
                        ' Verifica se a descri��o ultrapassa o limite e adiciona ao aviso
                        If ApproximateWidth(descRaw) > MAX_DESC_WIDTH Then
                            If Not gLongDesc.Exists(uniqueKey) Then gLongDesc.Add uniqueKey, descRaw
                        End If
                    End If
                End If
            End If
        End If
    End If
    
    Dim kids As Variant: kids = comp.GetChildren
    If IsArray(kids) Then
        Dim i As Long
        For i = LBound(kids) To UBound(kids)
            Dim child As Object: Set child = kids(i)
            TraverseComponent child, dict, False
        Next i
    End If
End Sub

' ===================== NOVAS FUN��ES DE RELAT�RIO E LARGURA =====================
Private Sub ReportMissingDescriptions(ByVal missing As Object)
    Dim msg As String, k As Variant, n As Long
    msg = "ERRO: Os seguintes c�digos est�o com a descri��o vazia (" & CStr(missing.Count) & "):" & vbCrLf & vbCrLf
    For Each k In missing.Keys
        n = n + 1
        If n > 100 Then
            msg = msg & "... (" & CStr(missing.Count - 100) & " mais)" & vbCrLf: Exit For
        End If
        msg = msg & CStr(k) & vbCrLf
    Next k
    MsgBox msg, vbCritical, "Descri��o Obrigat�ria Ausente"
End Sub

Private Sub ReportLongDescriptions(ByVal longDescs As Object)
    Dim msg As String, k As Variant, n As Long
    msg = "AVISO: As seguintes descri��es excedem a largura permitida (foram inclu�das no CSV):" & vbCrLf & vbCrLf
    For Each k In longDescs.Keys
        n = n + 1
        If n > 100 Then
            msg = msg & "... (" & CStr(longDescs.Count - 100) & " mais)" & vbCrLf: Exit For
        End If
        msg = msg & CStr(k) & " (Largura Aprox.: " & ApproximateWidth(longDescs(k)) & ")" & vbCrLf
    Next k
    MsgBox msg, vbExclamation, "Descri��o Muito Larga"
End Sub

' Calcula uma largura estimada para a string, considerando caracteres largos.
Private Function ApproximateWidth(s As String) As Long
    Dim width As Long
    Dim i As Long, ch As String
    
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        ' Caracteres largos comuns recebem peso 1.4, outros peso 1.
        ' Ajuste esta lista ou os pesos se necess�rio.
        Select Case UCase$(ch)
            Case "M", "W", "G", "@", "#", "$", "%", "&"
                width = width + 1.4
            Case "I", "J", "L", "T", "F", "1", "!", ".", ",", ";", ":"
                width = width + 0.8
            Case Else
                width = width + 1
        End Select
    Next i
    ApproximateWidth = Round(width)
End Function
' ==============================================================================

Private Sub WriteCsv(path As String, dict As Object)
    Dim f As Integer: f = FreeFile
    Open path For Output As #f
    
    ' Debug: Mostrar conte�do do dicion�rio
    Debug.Print "=== CONTE�DO DO DICION�RIO ==="
    Debug.Print "Total de itens no dict: " & dict.Count
    
    ' Criar array com as chaves ordenadas alfabeticamente
    Dim keysArray() As String
    Dim keyCount As Long: keyCount = dict.Count
    ReDim keysArray(0 To keyCount - 1)
    
    Dim i As Long: i = 0
    Dim k As Variant
    For Each k In dict.Keys
        keysArray(i) = CStr(k)
        Debug.Print "Dict Key " & i & ": " & keysArray(i) & " -> " & dict(keysArray(i))
        i = i + 1
    Next k
    
    ' Ordenar o array alfabeticamente
    Call QuickSort(keysArray, 0, keyCount - 1)
    
    Debug.Print "=== AP�S ORDENA��O ==="
    For i = 0 To keyCount - 1
        Debug.Print "Sorted " & i & ": " & keysArray(i)
    Next i
    
    ' Escrever o CSV com as chaves ordenadas, detectando duplicatas
    Debug.Print "=== ESCREVENDO CSV ==="
    Dim writtenCodes As Object: Set writtenCodes = CreateObject("Scripting.Dictionary")
    writtenCodes.CompareMode = vbTextCompare
    Dim duplicateCount As Long: duplicateCount = 0
    Dim duplicateMsg As String: duplicateMsg = ""
    
    For i = 0 To keyCount - 1
        ' Extrair apenas a parte do c�digo (antes do primeiro "|") para o CSV
        Dim csvCode As String: csvCode = keysArray(i)
        Dim pipePos As Long: pipePos = InStr(csvCode, "|")
        If pipePos > 0 Then csvCode = Left$(csvCode, pipePos - 1)
        
        ' Verificar se este c�digo j� foi escrito
        If writtenCodes.Exists(csvCode) Then
            ' Duplicata encontrada - n�o escrever e reportar
            duplicateCount = duplicateCount + 1
            duplicateMsg = duplicateMsg & "DUPLICATA EXCLU�DA: " & csvCode & " - " & dict(keysArray(i)) & vbCrLf
            Debug.Print "DUPLICATA EXCLU�DA: " & csvCode & " | " & dict(keysArray(i))
        Else
            ' C�digo �nico - escrever no CSV
            writtenCodes.Add csvCode, ""
            Debug.Print "CSV: " & csvCode & " | " & dict(keysArray(i))
            Print #f, CsvField(CStr(csvCode)) & DELIM & CsvField(CStr(dict(keysArray(i))))
        End If
    Next i
    
    ' Mostrar relat�rio de duplicatas
    If duplicateCount > 0 Then
        Debug.Print "=== RELAT�RIO DE DUPLICATAS ==="
        Debug.Print "Total de duplicatas exclu�das: " & duplicateCount
        Debug.Print duplicateMsg
        MsgBox "Foram encontrados e exclu�dos " & duplicateCount & " itens duplicados no CSV." & vbCrLf & vbCrLf & _
               "Duplicatas exclu�das:" & vbCrLf & Left$(duplicateMsg, 500) & IIf(Len(duplicateMsg) > 500, "...", ""), _
               vbInformation, "Duplicatas Removidas"
    End If
    Close #f
End Sub
Private Function GetConfigurationPartNumber(cfg As Object, md As Object) As String
    On Error Resume Next
    If cfg Is Nothing Then Exit Function
    
    ' Debug: Mostrar informa��es da configura��o
    Debug.Print "    BOMPartNoSource: " & cfg.BOMPartNoSource
    Debug.Print "    Config Name: " & cfg.Name
    Debug.Print "    AlternateName: " & cfg.AlternateName
    
    ' M�todo 1: Tentar obter o Part Number diretamente da configura��o
    Dim partNumber As String
    partNumber = cfg.GetPartNumber
    
    If Len(Trim$(partNumber)) > 0 Then
        Debug.Print "    GetPartNumber(): " & partNumber
        GetConfigurationPartNumber = partNumber
        Exit Function
    End If
    
    ' M�todo 1.5: Se BOMPartNoSource for 0, usar o nome da configura��o
    If cfg.BOMPartNoSource = 0 Then
        Debug.Print "    Usando nome da config: " & cfg.Name
        GetConfigurationPartNumber = cfg.Name
        Exit Function
    End If
    
    ' M�todo 1.6: Se AlternateName estiver preenchido, usar ele (independente do BOMPartNoSource)
    If Len(Trim$(cfg.AlternateName)) > 0 Then
        Debug.Print "    Usando AlternateName: " & cfg.AlternateName
        GetConfigurationPartNumber = cfg.AlternateName
        Exit Function
    End If
    
    ' M�todo 2: Tentar propriedades personalizadas espec�ficas
    Dim ext As Object: Set ext = md.Extension
    Dim mgr As Object: Set mgr = ext.CustomPropertyManager(cfg.Name)
    
    ' Tentar diferentes nomes de propriedade
    Dim propNames() As String
    propNames = Split("Part Number;PartNumber;Part_Number;N�mero de pe�a;Numero de pe�a", ";")
    
    Dim i As Long, val As String, valOut As String, ok As Boolean
    For i = LBound(propNames) To UBound(propNames)
        ok = mgr.Get4(propNames(i), False, val, valOut)
        Debug.Print "    Prop '" & propNames(i) & "': " & IIf(ok, valOut, "N�O ENCONTRADA")
        If ok And Len(Trim$(valOut)) > 0 Then
            GetConfigurationPartNumber = valOut
            Exit Function
        End If
    Next i
    
    ' M�todo 3: Tentar no n�vel do documento (sem configura��o espec�fica)
    Set mgr = ext.CustomPropertyManager("")
    For i = LBound(propNames) To UBound(propNames)
        ok = mgr.Get4(propNames(i), False, val, valOut)
        Debug.Print "    Prop '" & propNames(i) & "' (doc): " & IIf(ok, valOut, "N�O ENCONTRADA")
        If ok And Len(Trim$(valOut)) > 0 Then
            GetConfigurationPartNumber = valOut
            Exit Function
        End If
    Next i
    
    GetConfigurationPartNumber = ""
    On Error GoTo 0
End Function

Private Function GetBOMPartNumber(cfg As Object, md As Object) As String
    If cfg Is Nothing Then Exit Function
    Select Case cfg.BOMPartNoSource
        Case 0: GetBOMPartNumber = cfg.Name
        Case 1: GetBOMPartNumber = BaseName(md.GetPathName)
        Case 2: GetBOMPartNumber = cfg.AlternateName
        Case 3:
            Dim p As Object: Set p = cfg.GetParent
            If Not p Is Nothing Then GetBOMPartNumber = IIf(Len(p.AlternateName) > 0, p.AlternateName, p.Name)
        Case Else: GetBOMPartNumber = ""
    End Select
End Function
Private Function GetFirstProp(ByVal md As Object, ByVal cfgName As String, ByRef candidates() As String) As String
    On Error Resume Next
    Dim ext As Object: Set ext = md.Extension
    Dim mgr As Object, i As Long, val As String, valOut As String, ok As Boolean
    
    ' Debug: Mostrar todas as propriedades dispon�veis
    Debug.Print "  Buscando propriedades para config: " & cfgName
    
    Set mgr = ext.CustomPropertyManager(cfgName)
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, val, valOut)
        Debug.Print "    Tentando '" & candidates(i) & "': " & IIf(ok, valOut, "N�O ENCONTRADA")
        If ok And Len(Trim$(valOut)) > 0 Then GetFirstProp = valOut: Exit Function
    Next i
    
    Set mgr = ext.CustomPropertyManager("")
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, val, valOut)
        Debug.Print "    Tentando '" & candidates(i) & "' (sem config): " & IIf(ok, valOut, "N�O ENCONTRADA")
        If ok And Len(Trim$(valOut)) > 0 Then GetFirstProp = valOut: Exit Function
    Next i
    GetFirstProp = ""
    On Error GoTo 0
End Function
Private Function CleanCode(ByVal s As String) As String
    Dim temp As String: temp = Replace(s, " ", ""): temp = Replace(temp, "-", "")
    Dim upperTemp As String: upperTemp = UCase$(temp)
    If Not (Right$(upperTemp, 1) = "M" Or Right$(upperTemp, 2) = "E1" Or Right$(upperTemp, 2) = "E2") Then
        temp = Replace(temp, "OL", "", 1, -1, vbTextCompare)
    End If
    CleanCode = temp
End Function
Private Function SanitizeName(ByVal s As String) As String
    Dim bad As String: bad = "~""#%&*:<>?{|}/\[];" & Chr$(10) & Chr$(13)
    Dim i As Long
    For i = 1 To Len(bad): s = Replace$(s, Mid$(bad, i, 1), "_"): Next i
    SanitizeName = Trim$(s)
End Function
Private Function EnsureDesktopCadastroEquipFolder(ByVal codigoRaiz As String) As String
    Dim desktopPath As String: desktopPath = Environ$("USERPROFILE") & "\Desktop"
    Dim rootFolder As String: rootFolder = desktopPath & "\CADASTRO DE EQUIPAMENTOS"
    If Len(Dir$(rootFolder, vbDirectory)) = 0 Then MkDir rootFolder
    Dim subFolder As String: subFolder = rootFolder & "\CADASTRO " & codigoRaiz
    If Len(Dir$(subFolder, vbDirectory)) = 0 Then MkDir subFolder
    EnsureDesktopCadastroEquipFolder = subFolder
End Function
Private Function BuildDesktopCadastroEquipCsvPath(ByVal codigoRaiz As String, ByVal nomeArquivo As String) As String
    Dim folderPath As String: folderPath = EnsureDesktopCadastroEquipFolder(codigoRaiz)
    If Right$(folderPath, 1) <> "\" Then folderPath = folderPath & "\"
    BuildDesktopCadastroEquipCsvPath = folderPath & SanitizeName(nomeArquivo)
End Function
Private Function CsvField(ByVal s As String) As String
    If InStr(s, DELIM) Or InStr(s, """") Or InStr(s, vbCr) Or InStr(s, vbLf) Then
        CsvField = """" & Replace(s, """", """""") & """"
    Else
        CsvField = s
    End If
End Function
Private Function BaseName(fullPath As String) As String
    Dim i As Long: i = InStrRev(fullPath, "\")
    If i > 0 Then BaseName = Mid$(fullPath, i + 1) Else BaseName = fullPath
    Dim p As Long: p = InStrRev(BaseName, ".")
    If p > 0 Then BaseName = Left$(BaseName, p - 1) Else BaseName = BaseName
End Function
Private Function IsSuppressedSafe(comp As Object) As Boolean
    On Error Resume Next: IsSuppressedSafe = comp.IsSuppressed: On Error GoTo 0
End Function

Private Function IsExcludedFromBOM(comp As Object, cfg As Object) As Boolean
    On Error Resume Next
    
    ' Verificar se o componente est� marcado para ser exclu�do da lista de materiais
    ' O m�todo GetBOMBehavior retorna:
    ' 0 = Include in BOM
    ' 1 = Exclude from BOM
    ' 2 = Exclude from BOM if configured to do so
    
    Dim bomBehavior As Long
    bomBehavior = comp.GetBOMBehavior
    
    ' Se o comportamento for 1 (Exclude from BOM), retorna True
    If bomBehavior = 1 Then
        IsExcludedFromBOM = True
        Exit Function
    End If
    
    ' Se o comportamento for 2, verificar se est� configurado para excluir
    If bomBehavior = 2 Then
        ' Verificar se a configura��o est� marcada para excluir
        Dim excludeFromBOM As Boolean
        excludeFromBOM = cfg.GetExcludeFromBOM
        IsExcludedFromBOM = excludeFromBOM
        Exit Function
    End If
    
    ' Caso contr�rio, incluir no BOM
    IsExcludedFromBOM = False
    On Error GoTo 0
End Function

Private Sub QuickSort(ByRef arr() As String, ByVal low As Long, ByVal high As Long)
    If low < high Then
        Dim pi As Long: pi = Partition(arr, low, high)
        Call QuickSort(arr, low, pi - 1)
        Call QuickSort(arr, pi + 1, high)
    End If
End Sub

Private Function Partition(ByRef arr() As String, ByVal low As Long, ByVal high As Long) As Long
    Dim pivot As String: pivot = arr(high)
    Dim i As Long: i = low - 1
    Dim j As Long
    
    For j = low To high - 1
        If StrComp(arr(j), pivot, vbTextCompare) <= 0 Then
            i = i + 1
            Dim temp As String: temp = arr(i): arr(i) = arr(j): arr(j) = temp
        End If
    Next j
    
    temp = arr(i + 1): arr(i + 1) = arr(high): arr(high) = temp
    Partition = i + 1
End Function

' =============== VERIFICA��O DE LETRA F ===============
Private Sub CheckForLetterF(ByRef dict As Object)
    Dim codesWithF As Object: Set codesWithF = CreateObject("Scripting.Dictionary")
    codesWithF.CompareMode = vbTextCompare
    
    Dim k As Variant
    For Each k In dict.Keys
        ' Extrair apenas a parte do c�digo (antes do primeiro "|") para verificar
        Dim codeToCheck As String: codeToCheck = CStr(k)
        Dim pipePos As Long: pipePos = InStr(codeToCheck, "|")
        If pipePos > 0 Then codeToCheck = Left$(codeToCheck, pipePos - 1)
        
        If InStr(1, codeToCheck, "F", vbTextCompare) > 0 Then
            codesWithF.Add codeToCheck, dict(k)
        End If
    Next k
    
    If codesWithF.Count > 0 Then
        Dim msg As String: msg = "ATEN��O: Foram encontrados " & codesWithF.Count & " c�digos contendo a letra 'F':" & vbCrLf & vbCrLf
        For Each k In codesWithF.Keys
            msg = msg & "� " & k & " - " & codesWithF(k) & vbCrLf
        Next k
        MsgBox msg, vbExclamation, "C�digos com Letra F Detectados"
    End If
End Sub

