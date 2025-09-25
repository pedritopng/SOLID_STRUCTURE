
' MACRO PARA CADASTRAR PEÇAS E MONTAGENS

' Coluna A: Codigo (sem "OL", "-" e " ")
' Coluna B: Descricao
' Colunas C–I: "3","4","107","108","16","3","S"
' Coluna J: Peso do componente (separado por .)
' Detecção de código de equipamento final mantendo OL
' Exclui linhas cujo CODIGO contenha "^"
' Inclui peças fabricadas e submontagens
' Verifica se tem alguma descrição vazia e avisa quais são
' Verifica se alguma descrição ultrapassou o limite de caracteres
' NÃO inclui duplicatas
' NÃO Inclui peças OLZ

' Vai no Importador com o código 1 e Encoding UTF-8

Option Explicit
' ======= OPCOES =======
Const MAX_DESC_WIDTH As Long = 80                ' Limite de LARGURA APROXIMADA para a descrição
Const DELIM As String = ";"                      ' Delimitador CSV
' Propriedades candidatas
Dim CODE_PROPS() As String
Dim DESC_PROPS() As String
' Coletores globais
Dim gMissingDesc As Object                       ' Dicionário para descrições vazias
Dim gLongDesc As Object                          ' Dicionário para descrições longas (em largura)

Private Sub InitPropNames()
    CODE_PROPS = Split("Código;Codigo;Part Number;Número;Number", ";")
    DESC_PROPS = Split("Descrição;Description;Descritivo;Desc", ";")
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
    
    ' Inicializa os coletores de validação
    Set gMissingDesc = CreateObject("Scripting.Dictionary")
    gMissingDesc.CompareMode = vbTextCompare
    Set gLongDesc = CreateObject("Scripting.Dictionary")
    gLongDesc.CompareMode = vbTextCompare
    
    Dim swConf As Object, root As Object
    Set swConf = swModel.GetActiveConfiguration
    Set root = swConf.GetRootComponent3(True)
    If root Is Nothing Then
        MsgBox "Montagem sem componente raiz válido."
        Exit Sub
    End If
    TraverseComponent root, dict, True
    
    ' Validação crítica: Descrição vazia
    If gMissingDesc.Count > 0 Then
        ReportMissingDescriptions gMissingDesc
        MsgBox "O processo foi interrompido. Corrija os itens com descrição vazia antes de continuar.", vbCritical, "Geração de Arquivo Cancelada"
        Exit Sub
    End If
    
    ' Aviso: Descrição longa
    If gLongDesc.Count > 0 Then
        ReportLongDescriptions gLongDesc
    End If
    
    ' Verificação: Letra F nos códigos
    CheckForLetterF dict
    
    If dict.Count = 0 Then
        MsgBox "Nenhuma peça ou submontagem com descrição válida foi encontrada para gerar o arquivo.", vbInformation
        Exit Sub
    End If
    
    Dim asmCodeRaw As String
    asmCodeRaw = GetBOMPartNumber(swModel.GetActiveConfiguration, swModel)
    If Len(Trim$(asmCodeRaw)) = 0 Then asmCodeRaw = GetFirstProp(swModel, swConf.Name, CODE_PROPS)
    If Len(Trim$(asmCodeRaw)) = 0 Then asmCodeRaw = BaseName(swModel.GetPathName)
    
    Dim safeCode As String: safeCode = SanitizeName(asmCodeRaw)
    Dim fileName As String: fileName = "CADASTRO DE PEÇAS " & safeCode & ".csv"
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
                codeRaw = GetBOMPartNumber(cfg, md)
                If Len(Trim$(codeRaw)) = 0 Then codeRaw = GetFirstProp(md, cfgName, CODE_PROPS)
                If Len(Trim$(codeRaw)) = 0 Then codeRaw = BaseName(md.GetPathName)
                descRaw = GetFirstProp(md, cfgName, DESC_PROPS)
                
                Dim codeClean As String: codeClean = CleanCode(codeRaw)
                
                If InStr(1, codeClean, "^", vbTextCompare) = 0 And InStr(1, codeClean, "Z", vbTextCompare) = 0 Then
                    ' --- VALIDAÇÃO DA DESCRIÇÃO ---
                    If Len(Trim$(descRaw)) = 0 Then
                        If Not gMissingDesc.Exists(codeClean) Then gMissingDesc.Add codeClean, ""
                    Else
                        ' Se a descrição não estiver vazia, adiciona ao dicionário (mesmo se for longa)
                        If Not dict.Exists(codeClean) Then
                            Dim payload As String
                            payload = descRaw & "|" & md.GetPathName & "|" & cfgName
                            dict.Add codeClean, payload
                        End If
                        
                        ' Verifica se a descrição ultrapassa o limite e adiciona ao aviso
                        If ApproximateWidth(descRaw) > MAX_DESC_WIDTH Then
                            If Not gLongDesc.Exists(codeClean) Then gLongDesc.Add codeClean, descRaw
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

' ===================== NOVAS FUNÇÕES DE RELATÓRIO E LARGURA =====================
Private Sub ReportMissingDescriptions(ByVal missing As Object)
    Dim msg As String, k As Variant, n As Long
    msg = "ERRO: Os seguintes códigos estão com a descrição vazia (" & CStr(missing.Count) & "):" & vbCrLf & vbCrLf
    For Each k In missing.Keys
        n = n + 1
        If n > 100 Then
            msg = msg & "... (" & CStr(missing.Count - 100) & " mais)" & vbCrLf: Exit For
        End If
        msg = msg & CStr(k) & vbCrLf
    Next k
    MsgBox msg, vbCritical, "Descrição Obrigatória Ausente"
End Sub

Private Sub ReportLongDescriptions(ByVal longDescs As Object)
    Dim msg As String, k As Variant, n As Long
    msg = "AVISO: As seguintes descrições excedem a largura permitida (foram incluídas no CSV):" & vbCrLf & vbCrLf
    For Each k In longDescs.Keys
        n = n + 1
        If n > 100 Then
            msg = msg & "... (" & CStr(longDescs.Count - 100) & " mais)" & vbCrLf: Exit For
        End If
        msg = msg & CStr(k) & " (Largura Aprox.: " & ApproximateWidth(longDescs(k)) & ")" & vbCrLf
    Next k
    MsgBox msg, vbExclamation, "Descrição Muito Larga"
End Sub

Private Function ApproximateWidth(s As String) As Long
    Dim width As Long, i As Long, ch As String
    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)
        Select Case UCase$(ch)
            Case "M", "W", "G", "@", "#", "$", "%", "&": width = width + 1.4
            Case "I", "J", "L", "T", "F", "1", "!", ".", ",", ";", ":": width = width + 0.8
            Case Else: width = width + 1
        End Select
    Next i
    ApproximateWidth = Round(width)
End Function
' ==============================================================================

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
    Set mgr = ext.CustomPropertyManager(cfgName)
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, val, valOut): If ok And Len(Trim$(valOut)) > 0 Then GetFirstProp = valOut: Exit Function
    Next i
    Set mgr = ext.CustomPropertyManager("")
    For i = LBound(candidates) To UBound(candidates)
        ok = mgr.Get4(candidates(i), False, val, valOut): If ok And Len(Trim$(valOut)) > 0 Then GetFirstProp = valOut: Exit Function
    Next i
    GetFirstProp = ""
    On Error GoTo 0
End Function
Private Function GetMassKgByFile(ByVal filePath As String, ByVal cfgName As String) As Double
    On Error Resume Next
    Dim v As Variant: v = Application.SldWorks.GetMassProperties2(filePath, cfgName, 1)
    If IsArray(v) And UBound(v) >= 5 Then GetMassKgByFile = CDbl(v(5))
    On Error GoTo 0
End Function

' *** FUNÇÃO CORRIGIDA ***
Private Function CleanCode(ByVal s As String) As String
    Dim temp As String: temp = Replace(s, " ", ""): temp = Replace(temp, "-", "")
    Dim upperTemp As String: upperTemp = UCase$(temp)
    If Not (Right$(upperTemp, 1) = "M" Or Right$(upperTemp, 2) = "E1" Or Right$(upperTemp, 2) = "E2") Then
        temp = Replace(temp, "OL", "", 1, -1, vbTextCompare)
    End If
    CleanCode = temp
End Function

Private Function BuildDesktopCadastroEquipCsvPath(ByVal codigoRaiz As String, ByVal nomeArquivo As String) As String
    Dim folderPath As String
    folderPath = Environ$("USERPROFILE") & "\Desktop\CADASTRO DE EQUIPAMENTOS\CADASTRO " & SanitizeName(codigoRaiz)
    If Len(Dir$(folderPath, vbDirectory)) = 0 Then MkDir folderPath
    BuildDesktopCadastroEquipCsvPath = folderPath & "\" & SanitizeName(nomeArquivo)
End Function
Private Sub WriteCsv(path As String, dict As Object)
    Dim f As Integer: f = FreeFile
    Open path For Output As #f
    
    ' Criar array com as chaves ordenadas alfabeticamente
    Dim keysArray() As String
    Dim keyCount As Long: keyCount = dict.Count
    ReDim keysArray(0 To keyCount - 1)
    
    Dim i As Long: i = 0
    Dim k As Variant
    For Each k In dict.Keys
        keysArray(i) = CStr(k)
        i = i + 1
    Next k
    
    ' Ordenar o array alfabeticamente
    Call QuickSort(keysArray, 0, keyCount - 1)
    
    ' Escrever o CSV com as chaves ordenadas
    For i = 0 To keyCount - 1
        Dim p() As String: p = Split(dict(keysArray(i)), "|")
        Dim desc As String, pth As String, cfg As String
        If UBound(p) >= 2 Then
            desc = p(0): pth = p(1): cfg = p(2)
        Else
            desc = dict(keysArray(i)): pth = "": cfg = ""
        End If
        
        Dim massKg As Double: massKg = GetMassKgByFile(pth, cfg)
        Dim massStr As String: massStr = RemoveTrailingZeros(Replace(Format(massKg, "0.00"), ",", "."))
        
        Print #f, CsvField(CStr(keysArray(i))) & DELIM & CsvField(CStr(desc)) & DELIM & "3" & DELIM & "4" & DELIM & "107" & DELIM & "108" & DELIM & "16" & DELIM & "3" & DELIM & "S" & DELIM & CsvField(massStr)
    Next i
    Close #f
End Sub
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
Private Function SanitizeName(ByVal s As String) As String
    Dim bad As String: bad = "~""#%&*:<>?{|}/\[];" & Chr$(10) & Chr$(13)
    Dim i As Long
    For i = 1 To Len(bad): s = Replace$(s, Mid$(bad, i, 1), "_"): Next i
    SanitizeName = Trim$(s)
End Function

Private Function RemoveTrailingZeros(ByVal numStr As String) As String
    ' Remove zeros à direita após o ponto decimal
    Dim result As String: result = Trim$(numStr)
    
    ' Se não tem ponto decimal, retorna como está
    If InStr(result, ".") = 0 Then
        RemoveTrailingZeros = result
        Exit Function
    End If
    
    ' Remove zeros à direita
    Do While Right$(result, 1) = "0" And Len(result) > 1
        result = Left$(result, Len(result) - 1)
    Loop
    
    ' Se sobrou apenas o ponto decimal, remove ele também
    If Right$(result, 1) = "." Then
        result = Left$(result, Len(result) - 1)
    End If
    
    RemoveTrailingZeros = result
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

' =============== VERIFICAÇÃO DE LETRA F ===============
Private Sub CheckForLetterF(ByRef dict As Object)
    Dim codesWithF As Object: Set codesWithF = CreateObject("Scripting.Dictionary")
    codesWithF.CompareMode = vbTextCompare
    
    Dim k As Variant
    For Each k In dict.Keys
        If InStr(1, CStr(k), "F", vbTextCompare) > 0 Then
            codesWithF.Add CStr(k), dict(k)
        End If
    Next k
    
    If codesWithF.Count > 0 Then
        Dim msg As String: msg = "ATENÇÃO: Foram encontrados " & codesWithF.Count & " códigos contendo a letra 'F':" & vbCrLf & vbCrLf
        For Each k In codesWithF.Keys
            msg = msg & "• " & k & " - " & codesWithF(k) & vbCrLf
        Next k
        MsgBox msg, vbExclamation, "Códigos com Letra F Detectados"
    End If
End Sub

