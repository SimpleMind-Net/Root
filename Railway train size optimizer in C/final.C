// * File:            EFC train optimizer.bas                                       *
// * Author:          Tito Livio Medeiros Cardoso                                   *
// * Project:         Carajas railroad (EFC) train-type Optimization                *
// * State:           1.20                                                          *
// * Creation Date:   17/11/2003                                                    *
// * Description:     This program implements a simple GUI for entrance of          *
// *                  optimization parameters for routine with the objective of     *
// *                  to find the train configuration that minimizes the costs of   *
// *                  HP, wagons, patios, teams and diesel. The used algorithm is   *
// *                  of exhaustive research.                                       *
// * Revision Log:                                                                  *
// *                  17/11/2003 1.00.00 - Initial development                      *
// *                  02/01/2004 1.10.00 - Enhanced options for input by INI file,  *
// *                                       calculation without new stations, small  *
// *                                       station size criteria                    *
// *                  05/01/2004 1.11.00 - Correct bug in calc without new stations *
// *                  28/01/2004 1.20.00 - Actualized default parameters, rebuilded *
// *                                       terminal´s models for Ponta da Madeira   *
// *                                       and Carajás. Abandoned calc without new  *
// *                                       stations.                                *
// **********************************************************************************
// Lcc-Win32 Code
// **********************************************************************************

#include <windows.h>    // Win32 Header File
#include <windowsx.h>   // Win32 Header File
#include <commctrl.h>   // Win32 Header File
#include <mmsystem.h>   // Win32 Header File
#include <shellapi.h>   // Win32 Header File
#include <shlobj.h>     // Win32 Header File
#include <richedit.h>   // Win32 Header File
#include <wchar.h>      // Win32 Header File
#include <objbase.h>    // Win32 Header File
#include <ocidl.h>      // Win32 Header File
#include <winuser.h>    // Win32 Header File
#include <conio.h>
#include <direct.h>
#include <ctype.h>
#include <io.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#include <stdlib.h>
#include <setjmp.h>
#include <time.h>
#include <stdarg.h>
#include <process.h>

// *************************************************
//            User Defined Constants
// *************************************************

#define ID_Button_load 117
#define ID_Button_run 118
#define ID_Button_exit 119
#define ID_Button_about 120
#define MYJ_CLASS struct _MYJ*
#define MYMTPA_CLASS struct _MYMTPA*
#define MYBLOCOS_CLASS struct _MYBLOCOS*
#define MYHP_CLASS struct _MYHP*
#define MYLOCOS_CLASS struct _MYLOCOS*
#define MYTBHP_CLASS struct _MYTBHP*
#define MYMARCHA_CLASS struct _MYMARCHA*
#define MYEE_CLASS struct _MYEE*
#define MYLINK_CLASS struct _MYLINK*
#define MYCICLO_CLASS struct _MYCICLO*
#define MYTPM_CLASS struct _MYTPM*
#define MYTREM_DIA_CLASS struct _MYTREM_DIA*
#define MYR_CLASS struct _MYR*
#define MYTB_CLASS struct _MYTB*
#define MYVG_CLASS struct _MYVG*
#define MYMKBF_CLASS struct _MYMKBF*
#define MYNECESS_CLASS struct _MYNECESS*
#define MYHELP_CLASS struct _MYHELP*
#define HDF_LEFT 0
#define HDF_RIGHT 1
#define HDF_CENTER 2
#define LVM_FIRST 4096
#define LVM_GETHEADER LVM_FIRST+31

// *************************************************
//          User Defined Types And Unions
// *************************************************
typedef struct _myJ
{
int  atual;
int  melhor[16];
int  locos[16];
int  vg[16];
double  tbhp[16];
int  locos_tot[16];
int  gdt[16];
int  extpatio[16];
int  novpatio[16];
int  mil_litros[16];
int  equipes[16];
"}myJ, *LPMYJ;"

typedef struct _myMTPA
{
double  minerio;
double  cg;
"}myMTPA, *LPMYMTPA;"

typedef struct _myblocos
{
int  expor;
int  retorno;
"}myblocos, *LPMYBLOCOS;"

typedef struct _myHP
{
int  expor;
int  retorno;
"}myHP, *LPMYHP;"

typedef struct _mylocos
{
int  minimo;
int  maximo;
int  expor;
int  expor_ant;
int  expor_c36;
int  expor_c44;
int  retorno;
"}mylocos, *LPMYLOCOS;"

typedef struct _mytbhp
{
double  minimo;
double  maximo;
double  expor;
double  retorno;
double  atual;
"}mytbhp, *LPMYTBHP;"

typedef struct _mymarcha
{
double  expor;
double  retorno;
"}mymarcha, *LPMYMARCHA;"

typedef struct _myEE
{
double  expor;
double  retorno;
"}myEE, *LPMYEE;"

typedef struct _mylink
{
double  expor;
double  retorno;
"}mylink, *LPMYLINK;"

typedef struct _myciclo
{
double  loco;
double  vagao;
"}myciclo, *LPMYCICLO;"

typedef struct _myTPM
{
double  loco;
double  vagao;
"}myTPM, *LPMYTPM;"

typedef struct _mytrem_dia
{
double  expor;
double  retorno;
double  cg_expor;
"}mytrem_dia, *LPMYTREM_DIA;"

typedef struct _myR
{
double  C36;
double  C44;
double  serie;
double  trem;
"}myR, *LPMYR;"

typedef struct _myTB
{
int  expor;
int  retorno;
"}myTB, *LPMYTB;"

typedef struct _myVG
{
int  expor;
int  expor_ant;
int  retorno;
"}myVG, *LPMYVG;"

typedef struct _myMKBF
{
int  C36;
int  C44;
"}myMKBF, *LPMYMKBF;"

typedef struct _mynecess
{
int  locos;
int  GDT;
int  patios;
int  diesel;
int  equipes;
int  locotrol;
"}mynecess, *LPMYNECESS;"

typedef struct _myhelp
{
double  HP[7];
double  C44[7];
double  ciclo[7];
double  necess;
"}myhelp, *LPMYHELP;"

// *************************************************
//                System Variables
// *************************************************

"char    CRLF[3]={13,10,0}; // Carr Rtn & Line Feed"
char    BCX_STR [1024*1024];
HHOOK  CmDlgHook;

// *************************************************
//            User Global Variables
// *************************************************
static HINSTANCE BCX_hInstance;
static int     BCX_ScaleX;
static int     BCX_ScaleY;
static char    BCX_ClassName[2048];
static int     help_2locos;
static double  passo_tbhp;
static double  asis_help;
static double  espera_cruz;
static double  asis_link;
static double  asis_avaria;
static double  asis_quebra;
static double  asis_PA;
static double  cks_recepcao_asis;
static double  cks_aguard_asis;
static double  cks_carga_asis;
static double  cks_formacao_asis;
static double  tmp_L56_CKS;
static double  tpm_recp_asis_lote1;
static double  tpm_recp_asis_lote2;
static double  tpm_recp_asis_lote3;
static double  tpm_ag_desc_asis;
static double  tpm_descarga_asis;
static double  tpm_desl_class;
static double  tpm_classif_asis;
static double  tpm_manut_asis;
static double  tpm_formacao_asis;
static double  tpm_ag_loco;
static double  tpm_ag_equipe;
static double  tpm_ag_licenca;
static double  inspecao_oficina;
static double  tmp_L01_TPM;
static double  custo_linha;
static int     tamanho_min_patio;
static int     DMSB;
static int     ext_seguranca;
static int     dist_marco_amv;
static int     l_vagao;
static int     l_loco;
static double  cte_colson;
static double  indisp_via;
static int     inv_loco_minerio;
static int     inv_loco_cg;
static int     vida_loco;
static int     vida_vg;
static int     frota_locos;
static int     frota_GDT;
static double  indisp_loco;
static double  indisp_vg;
static int     silos;
static int     recuperadoras;
static double  vazao_recup_silo;
static int     cks_L1;
static int     cks_L3;
static int     cks_L5;
static int     cks_L2;
static int     cap_virador;
static int     nr_virador;
static int     tpm_L1;
static int     tpm_L2;
static int     tpm_L8;
static double  R_AS_IS;
static int     mkbf_c36;
static int     mkbf_c44;
static int     ET_adm;
static int     ET_vida_infinita;
static int     ET_AS_IS;
static double  FrotaC36_FrotaTotal;
static int     tb_vg_expor;
static int     tb_vg_retorno;
static int     tu_vg_expor;
static int     tu_trem_cg;
static int     dias_ano;
static int     dias_ano_cg;
static double  outros_trens_dia;
static double  tr_dia_asis;
static HWND    Form1;
static HWND    Panel1;
static HWND    Label1;
static HWND    Label2;
static HWND    Label3;
static HWND    Label4;
static HWND    Label5;
static HWND    Label6;
static HWND    Label7;
static HWND    Retorno_menor;
static HWND    Rebocadas;
static HWND    Text_min_tbhp;
static HWND    Text_min_locos;
static HWND    Text_mtpa_minerio;
static HWND    Text_mtpa_cg;
static HWND    Text_max_tbhp;
static HWND    Text_max_locos;
static HWND    Button_load;
static HWND    Button_run;
static HWND    Button_exit;
static HWND    Button_about;
static HWND    Listview1;
static HWND    Progressbar1;
static char    FileName[2048];
static FILE*  Fp1;
static FILE*  fp1;
static FILE*  FP1;

// *************************************************
//               Standard Macros
// *************************************************
#define BOR |
"#define Show(Window)RedrawWindow(Window,0,0,0);ShowWindow(Window,SW_SHOW);"
#define VAL(a)(double)atof(a)
#define FINT(a)floor(a)
#define CDBL(a)((double)(a))

// *************************************************
//               Standard Prototypes
// *************************************************
"HWND    BCX_Form(char*,int=0,int=0,int=250,int=150,int=0,int=0);"
"HWND    BCX_Input(char*,HWND,int,int,int,int,int,int=0,int=-1);"
"HWND    BCX_Button(char*,HWND,int=0,int=0,int=0,int=0,int=0,int=0,int=-1);"
"HWND    BCX_Label(char*,HWND,int=0,int=0,int=0,int=0,int=0,int=0,int=0);"
"HWND    BCX_Checkbox(char*,HWND,int=0,int=0,int=0,int=0,int=0,int=0,int=0);"
"HWND    BCX_ListView(char*,HWND,int,int,int,int,int,int=0,int=-1);"
"HWND    BCX_Control (char*,HWND,char*,int,int,int,int,int,int=0,int=0);"
"HWND    BCX_ProgressBar (char*,HWND,int=0,int=0,int=0,int=0,int=0,int=0,int=-1);"
char*   BCX_Get_Text(HWND);
"int     BCX_Set_Text(HWND,char*);"
"void    Center (HWND,HWND=0,HWND=0);"
char*   BCX_TmpStr(size_t);
"char*   Using (char*,double);"
"char*   right (char*,int);"
char*   str (double);
"HOOKPROC CALLBACK SBProc (UINT, WPARAM, LPARAM);"
"char*    GetFileName(char*,char*,int=0,HWND=0,DWORD=0,char*=0);"
"char*   join (int, ... );"
"int     instr(char*,char*,int=0,int=0);"
"char    *_stristr_(char*,char*);"
"int     MsgBox (char*,char*,int);"
int     EoF (FILE*);
BOOL    Exist   (char*);
BOOL    Exist_A (char*);
BOOL    Exist_B (char*);
"double  Round (double,int);"
double  Abs (double);
double  Exp (double);
"double  MIN (double,double);"
float   timer(void);

// *************************************************
//               User's Prototypes
// *************************************************
void    FormLoad (void);
"LRESULT CALLBACK WndProc (HWND, UINT, WPARAM, LPARAM);"
void    CmdExit (void);
void    Botao_Sobre_Click (void);
void    Button_load_Click (void);
void    Button_run_Click (void);
int     POSITIVO (int);
int     ARRED_PARA_CIMA (double);
"void    Set_ColumnText (HWND, int, char *);"
"void    BCX_LV_Reset (HWND, int, int);"
"void    BCX_LV_Justify (HANDLE, int, int);"

// *********************************
// Definition of GUI and its events
// *********************************
//**********************************
"int WINAPI WinMain(HINSTANCE hInst,HINSTANCE hPrev,LPSTR CmdLine,int CmdShow)"
{
WNDCLASS Wc;
MSG      Msg;
// *****************************
"strcpy(BCX_ClassName,""OptimizeEFC"");"
//***************************************
// Programmer has selected to use pixels
//***************************************
BCX_ScaleX       = 1;
BCX_ScaleY       = 1;
BCX_hInstance    =  hInst;
//******************************************************
Wc.style         =  CS_HREDRAW | CS_VREDRAW | CS_OWNDC;
Wc.lpfnWndProc   =  WndProc;
Wc.cbClsExtra    =  0;
Wc.cbWndExtra    =  0;
Wc.hInstance     =  hInst;
"Wc.hIcon         =  LoadIcon(hInst,MAKEINTRESOURCE(123));"
"Wc.hCursor       =  LoadCursor(NULL,IDC_ARROW);"
Wc.hbrBackground =  (HBRUSH)(COLOR_BTNFACE+1);
Wc.lpszMenuName  =  NULL;
Wc.lpszClassName =  BCX_ClassName;
RegisterClass(&Wc);

INITCOMMONCONTROLSEX iccex;
iccex.dwSize = sizeof(INITCOMMONCONTROLSEX);
//******************************************
iccex.dwICC =
ICC_LISTVIEW_CLASSES |
ICC_TREEVIEW_CLASSES |
ICC_BAR_CLASSES      |
ICC_TAB_CLASSES      |
ICC_UPDOWN_CLASS     |
ICC_PROGRESS_CLASS   |
ICC_USEREX_CLASSES   |
ICC_DATE_CLASSES;
InitCommonControlsEx(&iccex);

//******************************************
FormLoad();
//******************************************
"while(GetMessage(&Msg,NULL,0,0))"
{
HWND hActiveWindow = GetActiveWindow();
"if(!IsWindow(hActiveWindow) || !IsDialogMessage(hActiveWindow,&Msg))"
{
TranslateMessage(&Msg);
DispatchMessage(&Msg);
}
}
return Msg.wParam;
}

// *************************************************
//                 Run Time Functions
// *************************************************

char *BCX_TmpStr (size_t Bites)
{
static int   StrCnt;
static char *StrFunc[2048];
StrCnt=(StrCnt + 1) & 2047;
if(StrFunc[StrCnt]) free (StrFunc[StrCnt]);
"return StrFunc[StrCnt]=(char*)calloc(Bites+128,1);"
}

"char *right (char *S, int length)"
{
int tmplen = strlen(S);
char *BCX_RetStr = BCX_TmpStr(tmplen);
tmplen -= length;
if (tmplen<0) tmplen = 0;
"return strcpy(BCX_RetStr, S + tmplen);"
}

char *str (double d)
{
char *strtmp = BCX_TmpStr(16);
"sprintf(strtmp,""% .15g"",d);"
return strtmp;
}

"char * join(int n, ...)"
{
"register int i = n, tmplen = 0;"
char *s_;
char *strtmp = 0;
va_list marker;
"va_start(marker, n); // Initialize variable arguments"
while(i-- > 0)
{
"s_ = va_arg(marker, char *);"
tmplen += strlen(s_);
}
strtmp = BCX_TmpStr(tmplen);
va_end(marker); // Reset variable arguments
i = n;
"va_start(marker, n); // Initialize variable arguments"
while(i-- > 0)
{
"s_ = va_arg(marker, char *);"
"strtmp = strcat(strtmp, s_);"
}
va_end(marker); // Reset variable arguments
return strtmp;
}

"HOOKPROC CALLBACK SBProc (UINT Msg, WPARAM wParam, LPARAM lParam)"
{
if(Msg==HCBT_ACTIVATE)
{
static  RECT  rc1;
static  RECT  rc2;
"GetWindowRect(GetDesktopWindow(),&rc1);"
"GetWindowRect((HWND)wParam,&rc2);"
"SetWindowPos((HWND)wParam,HWND_TOP,(rc1.left+rc1.right-rc2.right+rc2.left)/2,"
"(rc1.top+rc1.bottom-rc2.bottom+rc2.top)/2,0,0,SWP_NOSIZE|SWP_NOACTIVATE);"
UnhookWindowsHookEx(CmDlgHook);
}
return 0;
}

"char *GetFileName(char*Title,char*Filter,int Flag,HWND hWnd,DWORD Flags,char*InitialDir)"
{
OPENFILENAME OpenFileStruct;
char* filename  = BCX_TmpStr(500000);
char* RET       = BCX_TmpStr(500000);
char* Extension = BCX_TmpStr(256);
char* filetitle = BCX_TmpStr(256);
char ch=0;
int Counter=0;
char *strtmp=0;

"memset(&OpenFileStruct,0,sizeof(OpenFileStruct));"
strtmp = BCX_TmpStr(500000);
"strcat(Extension,Filter);"

for(Counter=1;Counter<=strlen(Filter)-1;Counter++)
{
ch=Filter[Counter];
if(ch=='|')
Extension[Counter]=0;
else
Extension[Counter]=ch;
}
"CmDlgHook=SetWindowsHookEx(WH_CBT,(HOOKPROC)SBProc,(HINSTANCE)NULL,GetCurrentThreadId());"
OpenFileStruct.lStructSize=sizeof(OpenFileStruct);
OpenFileStruct.hwndOwner=hWnd;
OpenFileStruct.hInstance=0;
OpenFileStruct.lpstrFilter=Extension;
OpenFileStruct.lpstrTitle=Title;
OpenFileStruct.Flags=Flags;
OpenFileStruct.nMaxFile=500000;
OpenFileStruct.nMaxFileTitle=255;
OpenFileStruct.lpstrFile=filename;
OpenFileStruct.lpstrFileTitle=filetitle;
OpenFileStruct.lpstrCustomFilter=0;
OpenFileStruct.nMaxCustFilter=0;
OpenFileStruct.nFilterIndex=0;
OpenFileStruct.lpstrInitialDir=InitialDir;
OpenFileStruct.nFileOffset=0;
OpenFileStruct.nFileExtension=0;
OpenFileStruct.lpstrDefExt=0;
OpenFileStruct.lCustData=0;
OpenFileStruct.lpfnHook=0;
OpenFileStruct.lpTemplateName=0;
OpenFileStruct.Flags = OFN_HIDEREADONLY | OFN_CREATEPROMPT | OFN_EXPLORER;
if(!Flag)
{
if(GetOpenFileName(&OpenFileStruct))
{
int len=strlen(OpenFileStruct.lpstrFile);
if(OpenFileStruct.lpstrFile[len+1]==0)
"return strcpy(strtmp,OpenFileStruct.lpstrFile);"
else
{
"strcpy(RET,OpenFileStruct.lpstrFile);"
OpenFileStruct.lpstrFile+=len+1;
while(OpenFileStruct.lpstrFile[0])
{
len=strlen(OpenFileStruct.lpstrFile);
"sprintf(RET,""%s%s%s"",RET,"","",OpenFileStruct.lpstrFile);"
OpenFileStruct.lpstrFile+=len+1;
}
"return strcpy(strtmp,RET);"
}
}
}
else
{
if(GetSaveFileName(&OpenFileStruct))
"return strcpy(strtmp,OpenFileStruct.lpstrFile);"
}
"return strcpy(strtmp,"""");"
}


"char *Using (char *Mask, double Num)"
{
int Spaces = 0;
int CntDec = 0;
int Decimals = 0;
int Dollar = 0;
int i = 0;
char* BCX_RetStr ={0};
char Buf_1[100] ={0};
char Buf_2[100];
char* p = Mask;
char* r;
char c;
int len;
int f = 1;
while (*p)
{
if (*p == 36) Dollar++;
if (*p == 32) Spaces++;
if (*p == 32 || *p == 35) if (CntDec) Decimals++;
if (*p == 46) CntDec = 1;
p++;
}
switch (Decimals)
{
"case 0: sprintf(BCX_STR,""%1.0f"",Num); break;"
"case 1: sprintf(BCX_STR,""%1.1f"",Num); break;"
"case 2: sprintf(BCX_STR,""%1.2f"",Num); break;"
"case 3: sprintf(BCX_STR,""%1.3f"",Num); break;"
"case 4: sprintf(BCX_STR,""%1.4f"",Num); break;"
"case 5: sprintf(BCX_STR,""%1.5f"",Num); break;"
"case 6: sprintf(BCX_STR,""%1.6f"",Num); break;"
"case 7: sprintf(BCX_STR,""%1.7f"",Num); break;"
"case 8: sprintf(BCX_STR,""%1.8f"",Num); break;"
"case 9: sprintf(BCX_STR,""%1.9f"",Num); break;"
"case 10: sprintf(BCX_STR,""%1.10f"",Num); break;"
"case 11: sprintf(BCX_STR,""%1.11f"",Num); break;"
"case 12: sprintf(BCX_STR,""%1.12f"",Num); break;"
"case 13: sprintf(BCX_STR,""%1.13f"",Num); break;"
"case 14: sprintf(BCX_STR,""%1.14f"",Num); break;"
"case 15: sprintf(BCX_STR,""%1.15f"",Num); break;"
"case 16: sprintf(BCX_STR,""%1.16f"",Num); break;"
}
"strcpy(Buf_2,BCX_STR);"
len = strlen(Buf_2);
"if (p = strchr(Buf_2, '.'))"
{
len = p - Buf_2;
}
"for (p = Buf_2, r = Buf_1; (c = *r++ = *p++);)"
if ((c== '.' ? f=0 : f) && --len && c != '-' && len % 3 == 0)
{
"*r++ = ',' ;"
}
"strcpy(BCX_STR,Buf_1);"
if(Dollar)
{
"memmove(BCX_STR+1,BCX_STR,strlen(BCX_STR)+1);"
BCX_STR[0]=36;
}
for(i=0;i<Spaces;i++)
{
"memmove(BCX_STR+1,BCX_STR,strlen(BCX_STR)+1);"
BCX_STR[0]=32;
}
BCX_RetStr = BCX_TmpStr(strlen(BCX_STR));
"strcpy(BCX_RetStr,BCX_STR);"
return BCX_RetStr;
}
"int instr(char* mane,char* match,int offset,int sensflag)"
{
char *s;
if (!mane || !match || ! *match || offset>(int)strlen(mane)) return 0;
if (sensflag)
"s = _stristr_(offset>0 ? mane+offset-1 : mane,match);"
else
"s = strstr (offset>0 ? mane+offset-1 : mane,match);"
return s ? (int)(s-mane)+1 : 0;
}

"char *_stristr_(char *String, char *Pattern)"
{
"char *pptr, *sptr, *start;"
"UINT  slen, plen;"
"for (start = (char *)String,"
"pptr  = (char *)Pattern,"
"slen  = strlen(String),"
plen  = strlen(Pattern);
slen >= plen;
"start++, slen--)"
{
while (toupper(*start) != toupper(*Pattern))
{
start++;
slen--;
if (slen < plen)
return(0);
}
sptr = start;
pptr = (char *)Pattern;
while (toupper(*sptr) == toupper(*pptr))
{
sptr++;
pptr++;
if (!*pptr) return (start);
}
}
return(0);
}

"double Round (double n, int d)"
{
"return (floor((n)*pow(10.0,(d))+0.5)/pow(10.0,(d)));"
}

BOOL Exist (char *szFilePath)
{
"if(instr(szFilePath,""*"")||instr(szFilePath,""?""))"
return Exist_A (szFilePath);
return Exist_B (szFilePath);
}

BOOL Exist_A (char *szFilePath)
{
WIN32_FIND_DATA W32FindData;
HANDLE rc;
"rc = FindFirstFile(szFilePath, &W32FindData);"
if(rc == INVALID_HANDLE_VALUE) return FALSE;
FindClose(rc);
return TRUE;
}

BOOL Exist_B (char *szFilePath)
{
DWORD ret;
ret = GetFileAttributes(szFilePath);
if (ret != 0xffffffff) return TRUE;
return FALSE;
}

float timer (void)
{
float tmp2;
int   tmp;
tmp = GetTickCount();
tmp2 = tmp/1000.0;
return tmp2;
}

double Exp (double arg)
{
"return pow(2.718281828459045,arg);"
}

double Abs (double a)
{
if(a<0) return -a;
return  a;
}

"double MIN (double a, double b)"
{
if(a<b)
return a;
return b;
}

int EoF (FILE* stream)
{
"register int c, status = ((c = fgetc(stream)) == EOF);"
"ungetc(c,stream);"
return status;
}

"int MsgBox (char *Msg, char *Title, int Num)"
{
"return MessageBox(GetActiveWindow(),Msg,Title,Num);"
}

"void Center (HWND hwnd, HWND Xhwnd, HWND Yhwnd)"
{
"RECT rect, rectP;"
"int  x, y, width, height;"
"int  screenwidth, screenheight;"
if(Xhwnd==0)
{
RECT  DesktopArea;
RECT  rc;
"SystemParametersInfo(SPI_GETWORKAREA,0,&DesktopArea,0);"
"GetWindowRect(hwnd,&rc);"
"SetWindowPos(hwnd,HWND_TOP,"
((DesktopArea.right-DesktopArea.left)-(rc.right-rc.left))/2+
"DesktopArea.left,((DesktopArea.bottom-DesktopArea.top)-"
"(rc.bottom-rc.top))/2 + DesktopArea.top,0,0,SWP_NOSIZE);"
return;
}
"GetWindowRect (hwnd,&rect);"
"GetWindowRect (Xhwnd,&rectP);"
width = rect.right-rect.left;
x = ((rectP.right-rectP.left)-width)/2 + rectP.left;
if(Yhwnd==NULL)
{
height = rect.bottom-rect.top;
y = ((rectP.bottom-rectP.top)-height)/2 + rectP.top;
}
else
{
"GetWindowRect(Yhwnd,&rectP);"
height = rect.bottom-rect.top;
y = ((rectP.bottom-rectP.top)-height)/2+rectP.top;
}
screenwidth = GetSystemMetrics(SM_CXSCREEN);
screenheight = GetSystemMetrics(SM_CYSCREEN);
if ((x<0)) x=0;
if ((y<0)) y=0;
if ((x+width>screenwidth))   x = screenwidth-width;
if ((y+height>screenheight)) y = screenheight-height;
"MoveWindow (hwnd, x, y, width, height, FALSE);"
}

HWND BCX_Form
"(char *Caption,"
"int X,"
"int Y,"
"int W,"
"int H,"
"int Style,"
int Exstyle)
{
HWND  A;
if(!Style)
{
Style= WS_MINIMIZEBOX  |
WS_SIZEBOX      |
WS_CAPTION      |
WS_MAXIMIZEBOX  |
WS_POPUP        |
WS_SYSMENU;
}
"A = CreateWindowEx(Exstyle,BCX_ClassName,Caption,"
"Style,"
"X*BCX_ScaleX,"
"Y*BCX_ScaleY,"
"(4+W)*BCX_ScaleX,"
"(12+H)*BCX_ScaleY,"
"NULL,(HMENU)NULL,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
return A;
}

HWND BCX_Button
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
HWND  A;
if(!Style)
{
Style=WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON | WS_TABSTOP;
}
if(Exstyle==-1)
{
Exstyle=WS_EX_STATICEDGE;
}
"A = CreateWindowEx(Exstyle,""button"",Text,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
if (W==0)
{
HDC  hdc=GetDC(A);
SIZE  size;
"GetTextExtentPoint32(hdc,Text,strlen(Text),&size);"
"ReleaseDC(A,hdc);"
"MoveWindow(A,X*BCX_ScaleX,Y*BCX_ScaleY,size.cx+(size.cx*0.5),size.cy+(size.cy*0.32),TRUE);"
}
return A;
}

HWND BCX_Input
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
HWND  A;
if(!Style)
{
Style = WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_LEFT | ES_AUTOHSCROLL;
}
if(Exstyle==-1)
{
Exstyle = WS_EX_CLIENTEDGE;
}
"A = CreateWindowEx(Exstyle,""edit"",Text,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
return A;
}

HWND BCX_Label
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
HWND  A;
if(!Style)
{
Style=WS_CHILD | SS_NOTIFY | SS_LEFT | WS_VISIBLE;
}
"A = CreateWindowEx(Exstyle,""static"",Text,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
if (W==0)
{
HDC  hdc=GetDC(A);
SIZE  size;
"GetTextExtentPoint32(hdc,Text,strlen(Text),&size);"
"ReleaseDC(A,hdc);"
"MoveWindow(A,X*BCX_ScaleX,Y*BCX_ScaleY,size.cx,size.cy,TRUE);"
}
return A;
}

HWND BCX_Checkbox
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
HWND  A;
if(!Style)
{
Style=WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX | WS_TABSTOP;
}
"A = CreateWindowEx(Exstyle,""button"",Text,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
if (W==0)
{
HDC  hdc=GetDC(A);
SIZE  size;
"GetTextExtentPoint32(hdc,Text,strlen(Text),&size);"
"ReleaseDC(A,hdc);"
"MoveWindow(A,X*BCX_ScaleX,Y*BCX_ScaleY,size.cx,size.cy,TRUE);"
}
return A;
}

HWND BCX_ListView
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
LV_COLUMN lvCol;
LV_ITEM lvItem;
HWND A;
"int i, lvStyle;"
if(!Style) Style=WS_CHILD | WS_TABSTOP | WS_VISIBLE | 0x241 | WS_BORDER;
if(Exstyle==-1) Exstyle=WS_EX_CLIENTEDGE | LVS_EX_FULLROWSELECT;
"A = CreateWindowEx(Exstyle,""SysListView32"",NULL,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
lvStyle=LVS_EX_GRIDLINES|LVS_EX_FULLROWSELECT;
"SendMessage(A,(UINT)LVM_SETEXTENDEDLISTVIEWSTYLE,(WPARAM)0,(LPARAM)lvStyle);"
lvCol.mask = LVCF_FMT  | LVCF_WIDTH | LVCF_TEXT | LVCF_SUBITEM;
lvCol.fmt  = LVCFMT_LEFT;
for(i=0;i<15;i++)
{
lvCol.cx=65;
"lvCol.pszText = """";"
lvCol.iSubItem = i;
"ListView_InsertColumn(A,0,&lvCol);"
}
lvItem.mask = LVIF_TEXT;
return A;
}

HWND BCX_Control
"(char *Class,HWND hWnd,char *Caption,int id,int x,int y,int w,int h,int Style,int Exstyle)"
{
HWND A;
if(!Style)Style = WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS;
"A=CreateWindowEx(Exstyle,Class,Caption,Style,"
"x*BCX_ScaleX,"
"y*BCX_ScaleY,"
"w*BCX_ScaleX,"
"h*BCX_ScaleY,"
"hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,(UINT)WM_SETFONT,(WPARAM)GetStockObject"
"(DEFAULT_GUI_FONT),(LPARAM)MAKELPARAM(FALSE,0));"
return A;
}

HWND BCX_ProgressBar
"(char* Text,HWND hWnd,int id,int X,int Y,int W,int H,int Style,int Exstyle)"
{
HWND A;
if(!Style) Style=WS_CHILD|WS_VISIBLE;
if(Exstyle==-1) Exstyle=WS_EX_CLIENTEDGE;
"A = CreateWindowEx(Exstyle,""msctls_progress32"",Text,Style,"
"X*BCX_ScaleX, Y*BCX_ScaleY, W*BCX_ScaleX, H*BCX_ScaleY, hWnd,(HMENU)id,BCX_hInstance,NULL);"
"SendMessage(A,PBM_SETRANGE,0,MAKELONG(0,100));"
"SendMessage(A,PBM_SETSTEP,1,0 );"
return A;
}

char *BCX_Get_Text(HWND hWnd)
{
int tmpint;
tmpint = 1 + GetWindowTextLength(hWnd);
char *strtmp = BCX_TmpStr(tmpint);
"GetWindowText(hWnd,strtmp,tmpint);"
return strtmp;
}

"int BCX_Set_Text(HWND hWnd, char *Text)"
{
"return SetWindowText(hWnd,Text);"
}

// ************************************
//       User Subs and Functions
// ************************************

void FormLoad (void)
{
// **************************************************************************
"Form1=BCX_Form(""EFC iron Ore train optimizer"",235,101,380,430);"
"Panel1=BCX_Control(""STATIC"",Form1,""Parameters"",102,8,8,272,172,1342177543,65568);"
"Label1=BCX_Label(""Tonn/HP"",Panel1,103,16,24,56,16);"
"Label2=BCX_Label(""Locomotives"",Panel1,104,16,56,96,16);"
"Label3=BCX_Label(""Ton/yr iron ore"",Panel1,105,16,88,72,16);"
"Label4=BCX_Label(""Ton/yr cargo"",Panel1,106,16,120,72,16);"
"Retorno_menor=BCX_Checkbox(""Small return"",Panel1,107,10,144,80,24);"
"Rebocadas=BCX_Checkbox(""Trail loco"",Panel1,108,95,144,75,24);"
"Text_min_tbhp=BCX_Input(""1.475"",Panel1,109,112,16,48,24);"
"Text_min_locos=BCX_Input(""1"",Panel1,110,112,48,48,24);"
"Text_mtpa_minerio=BCX_Input(""70.5"",Panel1,111,112,80,48,24);"
"Text_mtpa_cg=BCX_Input(""5.9"",Panel1,112,112,112,48,24);"
"Label5=BCX_Label(""to"",Panel1,113,168,24,32,16);"
"Label6=BCX_Label(""to"",Panel1,114,168,56,32,16);"
"Text_max_tbhp=BCX_Input(""7.146"",Panel1,115,200,16,48,24);"
"Text_max_locos=BCX_Input(""6"",Panel1,116,200,48,48,24);"
"Button_load=BCX_Button(""INI File"",Form1,117,288,32,72,24);"
"Button_run=BCX_Button(""Run"",Form1,118,288,64,72,24);"
"Button_exit=BCX_Button(""Exit"",Form1,119,288,96,72,24);"
"Button_about=BCX_Button(""About"",Form1,120,288,128,72,24);"
"Listview1=BCX_ListView(""Listview1"",Form1,121,8,200,352,176);"
"Label7=BCX_Label(""15 better results:"",Form1,122,8,184,200,16);"
"Progressbar1=BCX_ProgressBar(""Progressbar1"",Form1,123,8,384,352,20,1342177281,131072);"
// **************************************************************************
"Set_ColumnText(Listview1,0,""Cost"");"
"Set_ColumnText(Listview1,1,""Locos"");"
"Set_ColumnText(Listview1,2,""Wagons"");"
"Set_ColumnText(Listview1,3,""Tonn/HP"");"
"Set_ColumnText(Listview1,4,""Total locos"");"
"Set_ColumnText(Listview1,5,""Total wagons"");"
"Set_ColumnText(Listview1,6,""Extended stations"");"
"Set_ColumnText(Listview1,7,""New stations"");"
"Set_ColumnText(Listview1,8,""Thousand liters"");"
"Set_ColumnText(Listview1,9,""Crews"");"
Center(Form1);
Show(Form1);
}

"LRESULT CALLBACK WndProc (HWND hWnd, UINT Msg, WPARAM wParam, LPARAM lParam)"
{
if(LOWORD(wParam)==ID_Button_load)
{
Button_load_Click();
}
if(LOWORD(wParam)==ID_Button_run)
{
Button_run_Click();
}
if(LOWORD(wParam)==ID_Button_exit)
{
CmdExit();
}
if(LOWORD(wParam)==ID_Button_about)
{
Botao_Sobre_Click();
}
if(Msg==WM_CLOSE)
{
CmdExit();
}
if(Msg==WM_DESTROY)
{
PostQuitMessage(0);
}
if(Msg==WM_DESTROY)
{
"UnregisterClass(BCX_ClassName,BCX_hInstance);"
PostQuitMessage(0);
}
"return DefWindowProc(hWnd,Msg,wParam,lParam);"
}

// *****************************************
// Execution routines with click of the buttons
// *****************************************
void CmdExit (void)
{
"if(MsgBox(""Its results are in the file SAIDA.CSV"",""End of simulation ?"",4)==IDYES)"
{
DestroyWindow(Form1);
}
}

void Botao_Sobre_Click (void)
{
static char Minhamsg[2048];
"memset(&Minhamsg,0,sizeof(Minhamsg));"
"sprintf(BCX_STR,""%s%s%s%s%s%s%s%s"",""EFC Iron Ore train optimizer"",CRLF,""05/01/04  -  version 1.20.00"",CRLF,""Freeware"",CRLF,CRLF,""Tito Livio Medeiros Cardoso"");"
"strcpy(Minhamsg,BCX_STR);"
"MessageBox (GetActiveWindow(),Minhamsg,""Sobre"",0+64);"
}

void Button_load_Click (void)
{
static char Mask[2048];
"memset(&Mask,0,sizeof(Mask));"
static char A[2048];
"memset(&A,0,sizeof(A));"
"strcpy(Mask,""Definition files(*.ini) |*.INI"");"
"strcpy(FileName,(char*)GetFileName(""Load optimization parameters"",Mask));"
if(Exist(FileName))
{
"if((Fp1=fopen(FileName,""r""))==0)"
{
"fprintf(stderr,""Can't open file %s\n"",FileName);exit(1);"
}
while(!EoF(Fp1))
{
A[0]=0;
"fgets(A,1048576,Fp1);"
if(A[strlen(A)-1]==10)A[strlen(A)-1]=0;
"if(instr(A,""MIN TB-HP""))"
{
"BCX_Set_Text(Text_min_tbhp,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MAX TB-HP""))"
{
"BCX_Set_Text(Text_max_tbhp,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MIN LOCOS""))"
{
"BCX_Set_Text(Text_min_locos,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MAX LOCOS""))"
{
"BCX_Set_Text(Text_max_locos,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MTPA MINERIO""))"
{
"BCX_Set_Text(Text_mtpa_minerio,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MTPA CG""))"
{
"BCX_Set_Text(Text_mtpa_cg,right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""RETORNO MENOR""))"
{
"SendMessage(Retorno_menor,(UINT)BM_SETCHECK,(WPARAM)BST_CHECKED,(LPARAM)0);"
"if(VAL(right(A,strlen(A)-instr(A,"":"")))==0)"
{
"SendMessage(Retorno_menor,(UINT)BM_SETCHECK,(WPARAM)BST_UNCHECKED,(LPARAM)0);"
}
}
"if(instr(A,""PERMITE REBOCADAS""))"
{
"SendMessage(Rebocadas,(UINT)BM_SETCHECK,(WPARAM)BST_CHECKED,(LPARAM)0);"
"if(VAL(right(A,strlen(A)-instr(A,"":"")))==0)"
{
"SendMessage(Rebocadas,(UINT)BM_SETCHECK,(WPARAM)BST_UNCHECKED,(LPARAM)0);"
}
}
"if(instr(A,""PASSO CALC. TB/HP""))"
{
"passo_tbhp=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""HELP A COM 2 LOCOS""))"
{
"help_2locos=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ACOPLAGEM DO HELP""))"
{
"asis_help=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ESPERA EM CRUZAMENTO""))"
{
"espera_cruz=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ESPERA LINK""))"
{
"asis_link=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""IMPACTO ATUAL AVARIA""))"
{
"asis_avaria=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""IMPACTO ATUAL QUEBRA""))"
{
"asis_quebra=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MANOBRA REFORMACAO PARAUAPEBAS""))"
{
"asis_PA=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL RECEPCAO EM CKS""))"
{
"cks_recepcao_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL AGUARD. CARR. CKS""))"
{
"cks_aguard_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL CKS CARREGAMENTO""))"
{
"cks_carga_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL FORMACAO EM CKS""))"
{
"cks_formacao_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL DE VIAGEM L56-CKS""))"
{
"tmp_L56_CKS=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MANOBRA TPM RECEPCAO (1o LOTE)""))"
{
"tpm_recp_asis_lote1=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MANOBRA TPM RECEPCAO (2o LOTE)""))"
{
"tpm_recp_asis_lote2=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MAN. TPM RECEPCAO (DEMAIS LOTES)""))"
{
"tpm_recp_asis_lote3=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM AG.DESC""))"
{
"tpm_ag_desc_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM DESCARGA""))"
{
"tpm_descarga_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL DESLOC. DUMPER/CLASS.""))"
{
"tpm_desl_class=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM CLASSIFICACAO""))"
{
"tpm_classif_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM MANUTENCAO""))"
{
"tpm_manut_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM FORMACAO""))"
{
"tpm_formacao_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM AGUARD. LOCO""))"
{
"tpm_ag_loco=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM AGUARD. EQUIPE""))"
{
"tpm_ag_equipe=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL TPM AGUARD. LICENCA""))"
{
"tpm_ag_licenca=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""INSPECAO OFICINA/ABASTEC. LOCOS""))"
{
"inspecao_oficina=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TMP ATUAL DE VIAGEM L01-TPM""))"
{
"tmp_L01_TPM=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""CUSTO LINHA/METRO""))"
{
"custo_linha=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MINIMO TAM.PATIO NOVO(VG)""))"
{
"tamanho_min_patio=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DIST.MARCO A SB""))"
{
"DMSB=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXT.SEGURANCA (m)""))"
{
"ext_seguranca=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DIST.MARCA A AMV""))"
{
"dist_marco_amv=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""COMPR. GDT (m)""))"
{
"l_vagao=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""COMPR. LOCO (m)""))"
{
"l_loco=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""CTE COLSON""))"
{
"cte_colson=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""INDISPONIB.VIA (h)""))"
{
"indisp_via=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""VALOR LOCO MINERIO""))"
{
"inv_loco_minerio=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""VALOR LOCO CG""))"
{
"inv_loco_cg=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""VIDA UTIL LOCOS""))"
{
"vida_loco=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""VIDA UTIL VAGOES""))"
{
"vida_vg=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""FROTA EXIST.LOCOS""))"
{
"frota_locos=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""FROTA EXIST.GDT""))"
{
"frota_GDT=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DISPONIBILIDADE LOCOS""))"
{
"indisp_loco=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DISPONIBILIDADE GDT""))"
{
"indisp_vg=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""SILOS""))"
{
"silos=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""RECUPERADORAS""))"
{
"recuperadoras=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""RAZAO DE VAZAO RECUP./SILO""))"
{
"vazao_recup_silo=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L1 PERA""))"
{
"cks_L1=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L3 PERA""))"
{
"cks_L3=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L5 PERA""))"
{
"cks_L5=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L2 PERA""))"
{
"cks_L2=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""CAPACIDADE VIRADOR""))"
{
"cap_virador=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""NR.VIRADORES""))"
{
"nr_virador=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L1 ENTRADA""))"
{
"tpm_L1=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L2 ACESSO DUMPER""))"
{
"tpm_L2=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""EXTENSAO L8 PATIO FORMACAO""))"
{
"tpm_L8=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""CONFIAB. AS IS""))"
{
"R_AS_IS=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MKBF C36 AS IS""))"
{
"mkbf_c36=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""MKBF C44 AS IS""))"
{
"mkbf_c44=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ESFORCO ADMISSIVEL""))"
{
"ET_adm=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ESF.VIDA INFINITA""))"
{
"ET_vida_infinita=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""ESFORCO AS IS""))"
{
"ET_AS_IS=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""FROTA C36 / C44+C36""))"
{
"FrotaC36_FrotaTotal=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TB/VG CARREGADO""))"
{
"tb_vg_expor=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TU GDT""))"
{
"tu_vg_expor=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TB/VG RETORNO""))"
{
"tb_vg_retorno=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""TU/TREM CG""))"
{
"tu_trem_cg=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DIAS/ANO MINERIO""))"
{
"dias_ano=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""DIAS/ANO CG""))"
{
"dias_ano_cg=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""OUTROS TRENS/DIA""))"
{
"outros_trens_dia=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
"if(instr(A,""PAR/DIA DE TREM-M ATUAL""))"
{
"tr_dia_asis=VAL(right(A,strlen(A)-instr(A,"":"")));"
}
}
if(Fp1)
{
fflush(Fp1);
fclose(Fp1);
}
}
}

void Button_run_Click (void)
{
// Definition of UDTs for use in the variables of the routine
// Definition of UDT with the characteristics of each group of allocated help
static  int  custo_loco;
"memset(&custo_loco,0,sizeof(custo_loco));"
static  BOOL  permite_retorno_menor;
"memset(&permite_retorno_menor,0,sizeof(permite_retorno_menor));"
static  BOOL  permite_rebocadas;
"memset(&permite_rebocadas,0,sizeof(permite_rebocadas));"
static  int  reb;
"memset(&reb,0,sizeof(reb));"
static  int  tamanho_retorno;
"memset(&tamanho_retorno,0,sizeof(tamanho_retorno));"
static  int  tamanho_novo_patio;
"memset(&tamanho_novo_patio,0,sizeof(tamanho_novo_patio));"
static  int  andamento;
"memset(&andamento,0,sizeof(andamento));"
static  float  inicio;
"memset(&inicio,0,sizeof(inicio));"
static  float  final;
"memset(&final,0,sizeof(final));"
static  float  elapsed;
"memset(&elapsed,0,sizeof(elapsed));"
static  int  k;
"memset(&k,0,sizeof(k));"
static  int  k1;
"memset(&k1,0,sizeof(k1));"
static  double  k2;
"memset(&k2,0,sizeof(k2));"
static  int  ITER;
"memset(&ITER,0,sizeof(ITER));"
static  int  total_ITER;
"memset(&total_ITER,0,sizeof(total_ITER));"
static  int  tr_falta_cap;
"memset(&tr_falta_cap,0,sizeof(tr_falta_cap));"
static  int  nr_helps;
"memset(&nr_helps,0,sizeof(nr_helps));"
static  double  rampa;
"memset(&rampa,0,sizeof(rampa));"
static  double  ET;
"memset(&ET,0,sizeof(ET));"
static  double  trem_malha_expor;
"memset(&trem_malha_expor,0,sizeof(trem_malha_expor));"
static  double  avaria;
"memset(&avaria,0,sizeof(avaria));"
static  double  quebra;
"memset(&quebra,0,sizeof(quebra));"
static  double  tmp_help;
"memset(&tmp_help,0,sizeof(tmp_help));"
static  double  cruzamento;
"memset(&cruzamento,0,sizeof(cruzamento));"
static  double  asis_cruz;
"memset(&asis_cruz,0,sizeof(asis_cruz));"
static  double  asis_cruz_0;
"memset(&asis_cruz_0,0,sizeof(asis_cruz_0));"
static  double  headway;
"memset(&headway,0,sizeof(headway));"
static  double  ocupacao;
"memset(&ocupacao,0,sizeof(ocupacao));"
static  double  PA;
"memset(&PA,0,sizeof(PA));"
static  double  CKS;
"memset(&CKS,0,sizeof(CKS));"
static  double  TT_expor;
"memset(&TT_expor,0,sizeof(TT_expor));"
static  int  sobra;
"memset(&sobra,0,sizeof(sobra));"
static  int  extensao_patios;
"memset(&extensao_patios,0,sizeof(extensao_patios));"
static  char  patios_a_ampliar[2048];
"memset(&patios_a_ampliar,0,sizeof(patios_a_ampliar));"
static  int  nr_patios_a_ampliar;
"memset(&nr_patios_a_ampliar,0,sizeof(nr_patios_a_ampliar));"
static  double  par_trem_dia;
"memset(&par_trem_dia,0,sizeof(par_trem_dia));"
static  double  cap_pares_trem;
"memset(&cap_pares_trem,0,sizeof(cap_pares_trem));"
static  int  novos_patios;
"memset(&novos_patios,0,sizeof(novos_patios));"
static  char  patios_a_construir[2048];
"memset(&patios_a_construir,0,sizeof(patios_a_construir));"
static  double  cks_aguard;
"memset(&cks_aguard,0,sizeof(cks_aguard));"
static  double  cks_carga;
"memset(&cks_carga,0,sizeof(cks_carga));"
static  double  cks_formacao;
"memset(&cks_formacao,0,sizeof(cks_formacao));"
static  int  lotes;
"memset(&lotes,0,sizeof(lotes));"
static  double  tpm_recepcao;
"memset(&tpm_recepcao,0,sizeof(tpm_recepcao));"
static  double  tpm_ag_desc;
"memset(&tpm_ag_desc,0,sizeof(tpm_ag_desc));"
static  double  tpm_classif;
"memset(&tpm_classif,0,sizeof(tpm_classif));"
static  double  tpm_manut;
"memset(&tpm_manut,0,sizeof(tpm_manut));"
static  double  tpm_ag_recep;
"memset(&tpm_ag_recep,0,sizeof(tpm_ag_recep));"
static  double  tpm_ag_form;
"memset(&tpm_ag_form,0,sizeof(tpm_ag_form));"
static char mymsg[2048];
"memset(&mymsg,0,sizeof(mymsg));"
static  struct _myJ  J;
"memset(&J,0,sizeof(J));"
static  struct _myMTPA  MTPA;
"memset(&MTPA,0,sizeof(MTPA));"
static  struct _myblocos  blocos;
"memset(&blocos,0,sizeof(blocos));"
static  struct _myHP  HP;
"memset(&HP,0,sizeof(HP));"
static  struct _mylocos  locos;
"memset(&locos,0,sizeof(locos));"
static  struct _mytbhp  tbhp;
"memset(&tbhp,0,sizeof(tbhp));"
static  struct _mymarcha  marcha;
"memset(&marcha,0,sizeof(marcha));"
static  struct _myEE  EE;
"memset(&EE,0,sizeof(EE));"
static  struct _mylink  link;
"memset(&link,0,sizeof(link));"
static  struct _myciclo  ciclo;
"memset(&ciclo,0,sizeof(ciclo));"
static  struct _myTPM  TPM;
"memset(&TPM,0,sizeof(TPM));"
static  struct _mytrem_dia  trem_dia;
"memset(&trem_dia,0,sizeof(trem_dia));"
static  struct _myR  R;
"memset(&R,0,sizeof(R));"
static  struct _myTB  TB;
"memset(&TB,0,sizeof(TB));"
static  struct _myVG  VG;
"memset(&VG,0,sizeof(VG));"
static  struct _myMKBF  MKBF;
"memset(&MKBF,0,sizeof(MKBF));"
static  struct _mynecess  necess;
"memset(&necess,0,sizeof(necess));"
static  struct _myhelp  help;
"memset(&help,0,sizeof(help));"
// characteristics definition of critical spaces of EFC
static double tbhp_inferior[]=
{
"0.000,  2.806,  3.632,  3.667,  3.701,  3.977,  4.080,  4.976,  5.010,  5.527,  6.801,  6.973"
};

static double tbhp_superior[]=
{
"2.806,  3.632,  3.667,  3.701,  3.977,  4.080,  4.976,  5.010,  5.527,  6.801,  6.973,  7.200"
};

static int trechos_falta_cap[]=
{
"0,      1,      2,      3,      4,      5,      7,      8,      9,     11,     12,     13"
};

static int trechos_nr_helps[]=
{
"0,      1,      2,      3,      3,      4,      4,      4,      5,      6,      6,      6"
};

static double ciclo_help[]=
{
"0.00, 7.80, 0.66, 0.48, 4.08, 1.32, 5.40, 9.00, 10.50, 0.36, 0.42, 10.50, 1.56, 6.00"
};

static double trechos_rampa[]=
{
"0.0037, 0.0037, 0.0027, 0.0026, 0.0026, 0.0024, 0.0023, 0.0018, 0.0018, 0.0017, 0.0015, 0.0012, 0.0008"
};

// characteristics definition of the built stations of EFC
static char   locacao[][2048]=
{
"""2"", ""3"", ""4"", ""5"", ""6"", ""7"", ""8"", ""9"", ""10"", ""11"", ""12"", ""13"", ""14"", ""15"", ""16"", ""17"", ""18"", ""19"", ""20"", ""21"","
"""23"", ""24"", ""25"", ""26"", ""27"", ""28"", ""30"", ""31"", ""33"", ""34"", ""36"", ""38"", ""39"", ""41"", ""42"", ""43"", ""44"", ""45"", ""46"","
"""47"", ""48"", ""49"", ""50"", ""51"", ""53"", ""54"", ""56"""
};

static int CTU[]=
{
"2496, 2769, 2482, 2296, 2302, 2263, 2300, 2303, 2254, 2298, 2306, 2301, 2359, 2307, 2302, 2267, 2299, 2296, 2305,"
"2273, 2304, 2300, 3217, 2224, 2781, 2298, 3468, 2303, 2299, 2312, 2299, 2171, 2296, 2301, 2500, 2263, 2299, 2295,"
"2299, 2282, 3026, 2307, 2293, 2300, 2176, 2302, 3103"
};

// characteristics definition of the 48 spaces among equal of built stations of EFC
static char   par[][2048]=
{
"""1-2"",    ""2-3"",  ""3-4"",  ""4-5"",  ""5-6"",  ""6-7"",  ""7-8"",  ""8-9"",  ""9-10"",""10-11"",""11-12"",""12-13"",""13-14"",""14-15"",""15-16"","
"""16-17"",""17-18"",""18-19"",""19-20"",""20-21"",""21-23"",""23-24"",""24-25"",""25-26"",""26-27"",""27-28"",""28-30"",""30-31"","
"""31-33"",""33-34"",""34-36"",""36-38"",""38-39"",""39-41"",""41-42"",""42-43"",""43-44"",""44-45"",""45-46"",""46-47"",""47-48"","
"""48-49"",""49-50"",""50-51"",""51-53"",""53-54"",""54-56"",""56-58"","""""
};

static double Headway_espor[]=
{
"0.018, 0.015, 0.012, 0.014, 0.014, 0.019, 0.016, 0.015, 0.015, 0.013, 0.014, 0.016, 0.032, 0.021, 0.015, 0.013, 0.013, 0.013, 0.013, 0.014, 0.024, 0.013, 0.016, 0.012, 0.013,"
"0.013, 0.023, 0.031, 0.061, 0.021, 0.042, 0.048, 0.022, 0.067, 0.024, 0.016, 0.016, 0.014, 0.018, 0.015, 0.041, 0.018, 0.014, 0.014, 0.025, 0.018, 0.023, 0.021"
};

static double Headway_retorno[]=
{
"0.013, 0.011, 0.015, 0.018, 0.018, 0.016, 0.016, 0.017, 0.019, 0.046, 0.017, 0.016, 0.017, 0.016, 0.018, 0.015, 0.015, 0.018, 0.015, 0.019, 0.032, 0.047, 0.021, 0.023, 0.026,"
"0.024, 0.025, 0.011, 0.018, 0.021, 0.026, 0.016, 0.015, 0.023, 0.014, 0.016, 0.018, 0.047, 0.016, 0.017, 0.022, 0.015, 0.017, 0.016, 0.034, 0.013, 0.029, 0.042"
};

// default values for some variables if no input from INI file
if(passo_tbhp==0)
{
passo_tbhp=.001;
}
if(asis_help==0)
{
asis_help=.50;
}
if(espera_cruz==0)
{
espera_cruz=.50;
}
if(asis_link==0)
{
asis_link=.667;
}
if(asis_avaria==0)
{
asis_avaria=1.11;
}
if(asis_quebra==0)
{
asis_quebra=.10;
}
if(asis_PA==0)
{
asis_PA=1.0;
}
if(cks_recepcao_asis==0)
{
cks_recepcao_asis=.52;
}
if(cks_aguard_asis==0)
{
cks_aguard_asis=1.56;
}
if(cks_carga_asis==0)
{
cks_carga_asis=2.52;
}
if(cks_formacao_asis==0)
{
cks_formacao_asis=.97;
}
if(tmp_L56_CKS==0)
{
tmp_L56_CKS=.67;
}
if(tpm_recp_asis_lote1==0)
{
tpm_recp_asis_lote1=.584;
}
if(tpm_recp_asis_lote2==0)
{
tpm_recp_asis_lote2=.334;
}
if(tpm_recp_asis_lote3==0)
{
tpm_recp_asis_lote3=.167;
}
if(tpm_ag_desc_asis==0)
{
tpm_ag_desc_asis=1.09;
}
if(tpm_descarga_asis==0)
{
tpm_descarga_asis=1.98;
}
if(tpm_desl_class==0)
{
tpm_desl_class=.2;
}
if(tpm_classif_asis==0)
{
tpm_classif_asis=1.00;
}
if(tpm_manut_asis==0)
{
tpm_manut_asis=.11;
}
if(tpm_formacao_asis==0)
{
tpm_formacao_asis=1.00;
}
if(tpm_ag_loco==0)
{
tpm_ag_loco=.03;
}
if(tpm_ag_equipe==0)
{
tpm_ag_equipe=.21;
}
if(tpm_ag_licenca==0)
{
tpm_ag_licenca=.15;
}
if(inspecao_oficina==0)
{
inspecao_oficina=2.74;
}
if(tmp_L01_TPM==0)
{
tmp_L01_TPM=.45;
}
if(custo_linha==0)
{
custo_linha=.500;
}
if(DMSB==0)
{
DMSB=5;
}
if(ext_seguranca==0)
{
ext_seguranca=20;
}
if(dist_marco_amv==0)
{
dist_marco_amv=250;
}
if(l_vagao==0)
{
l_vagao=10;
}
if(l_loco==0)
{
l_loco=22;
}
if(cte_colson==0)
{
cte_colson=.75;
}
if(indisp_via==0)
{
indisp_via=2;
}
if(inv_loco_minerio==0)
{
inv_loco_minerio=1970;
}
if(inv_loco_cg==0)
{
inv_loco_cg=600;
}
if(vida_loco==0)
{
vida_loco=12;
}
if(vida_vg==0)
{
vida_vg=30;
}
if(frota_locos==0)
{
frota_locos=82;
}
if(frota_GDT==0)
{
frota_GDT=5390;
}
if(indisp_loco==0)
{
indisp_loco=.78;
}
if(indisp_vg==0)
{
indisp_vg=.98;
}
if(silos==0)
{
silos=2;
}
if(recuperadoras==0)
{
recuperadoras=3;
}
if(vazao_recup_silo==0)
{
vazao_recup_silo=.333;
}
if(cks_L1==0)
{
cks_L1=4030;
}
if(cks_L3==0)
{
cks_L3=2668;
}
if(cks_L5==0)
{
cks_L5=2482;
}
if(cks_L2==0)
{
cks_L2=2954;
}
if(cap_virador==0)
{
cap_virador=120;
}
if(nr_virador==0)
{
nr_virador=2;
}
if(tpm_L1==0)
{
tpm_L1=3669;
}
if(tpm_L2==0)
{
tpm_L2=2177;
}
if(tpm_L8==0)
{
tpm_L8=2383;
}
if(R_AS_IS==0)
{
R_AS_IS=.8052;
}
if(mkbf_c36==0)
{
mkbf_c36=62000;
}
if(mkbf_c44==0)
{
mkbf_c44=72000;
}
if(ET_adm==0)
{
ET_adm=170;
}
if(ET_vida_infinita==0)
{
ET_vida_infinita=60;
}
if(ET_AS_IS==0)
{
ET_AS_IS=88;
}
if(FrotaC36_FrotaTotal==0)
{
FrotaC36_FrotaTotal=.5;
}
if(tb_vg_expor==0)
{
tb_vg_expor=124;
}
if(tb_vg_retorno==0)
{
tb_vg_retorno=20;
}
if(tu_vg_expor==0)
{
tu_vg_expor=102;
}
if(tu_trem_cg==0)
{
tu_trem_cg=4500;
}
if(dias_ano==0)
{
dias_ano=355;
}
if(dias_ano_cg==0)
{
dias_ano_cg=355;
}
if(outros_trens_dia==0)
{
outros_trens_dia=1;
}
if(tr_dia_asis==0)
{
tr_dia_asis=8.33;
}
// ### recover variables defined in the form ###
tbhp.minimo=VAL(BCX_Get_Text(Text_min_tbhp));
tbhp.maximo=VAL(BCX_Get_Text(Text_max_tbhp));
locos.minimo=VAL(BCX_Get_Text(Text_min_locos));
locos.maximo=VAL(BCX_Get_Text(Text_max_locos));
MTPA.minerio=VAL(BCX_Get_Text(Text_mtpa_minerio));
MTPA.cg=VAL(BCX_Get_Text(Text_mtpa_cg));
// User is verified he wants to calculate with smaller return
permite_retorno_menor=FALSE;
"k=SendMessage(Retorno_menor,(UINT)BM_GETCHECK,(WPARAM)0,(LPARAM)0);"
if(k==BST_CHECKED)
{
permite_retorno_menor=TRUE;
}
// User is verified he wants to calculate with trail locomotives
permite_rebocadas=FALSE;
"k=SendMessage(Rebocadas,(UINT)BM_GETCHECK,(WPARAM)0,(LPARAM)0);"
if(k==BST_CHECKED)
{
permite_rebocadas=TRUE;
}
// defines the maximum number of calculations
total_ITER=(locos.maximo-locos.minimo+1)*FINT((tbhp.maximo-tbhp.minimo)/passo_tbhp);
// initializes counters and the progress bar
J.melhor[0]=1000000000;
inicio=timer();
ITER=0;
andamento=0;
"SendMessage(Progressbar1,(UINT)PBM_SETPOS,(WPARAM)andamento,(LPARAM)0);"
"BCX_LV_Reset(Listview1,10,15);"
// Create/open file for calculation output
"if((fp1=fopen(""saida.csv"",""w""))==0)"
{
"fprintf(stderr,""Can't open file %s\n"",""saida.csv"");exit(1);"
}
"fprintf(fp1,""\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\""\n"",""locos.expor"",""HP.expor"",""expor_c36"",""expor_c44"",""trail locos"",""wagons.expor"",""Tonn.expor"",""tonn/hp.expor"",""blocks.expor"",""spaces_without_capacity"",""number_helps"",""help[1]"",""help[2]"",""help[3]"",""help[4]"",""help[5]"",""help[6]"",""help.cycle[1]"",""help.cycle[2]"",""help.cycle[3]"",""help.cycle[4]"",""help.cycle[5]"",""help.cycle[6]"",""locos for help"",""Ramp(%)"",""Tractor effort(ton)"",""locos.return"",""HP.return"",""Wagons.return"",""Tonn.return"",""tonn/hp.return"",""blocks.return"",""metrage_return"",""MKBF.C36"",""MKBF.C44"",""reliability.C36"",""reliability.C44"",""reliability.train"",""train/day.expor"",""train/day.return"",""Running time.expor"",""Running time.return"",""Failure"",""train division"",""coupling help"",""PA"",""Carajas"",""Ponta da Madeira Terminal.wagon"",""Ponta da Madeira Terminal.locos"",""crossing"",""cross event"",""cycle.wagon"",""cycle.locos"",""L/ktkb.expor"",""L/ktkb.return"",""nr.extended stations"",""extended stations name"",""new stations"",""spaces for new stations"",""Total locos"",""Total wagons"",""metrage stations"",""diesel(1000L)"",""crews"",""locotrol"",""J-Cost"");"
if(fp1)
{
fflush(fp1);
fclose(fp1);
}
// CALCULATION LOOPING FOR LOCOS AND TONN-HP
for(locos.expor=locos.minimo; locos.expor<=locos.maximo; locos.expor+=1)
{
"locos.expor_c36=Round(FrotaC36_FrotaTotal*locos.expor,0);"
locos.expor_c44=locos.expor-locos.expor_c36;
HP.expor=3600*locos.expor_c36+4400*locos.expor_c44;
for(tbhp.atual=tbhp.minimo; passo_tbhp>=0 ? tbhp.atual<=tbhp.maximo : tbhp.atual>=tbhp.maximo; tbhp.atual+=passo_tbhp)
{
ITER+=1;
"SetWindowText(Form1,(join( 3,""Processing "",Using(""#"",100*ITER/total_ITER),""%"")));"
TB.expor=tbhp.atual*HP.expor;
VG.expor=(TB.expor-180*locos.expor)/tb_vg_expor;
TB.expor=VG.expor*tb_vg_expor+180*locos.expor;
tbhp.expor=CDBL(TB.expor)/CDBL(HP.expor);
if(locos.expor==locos.expor_ant&&VG.expor==VG.expor_ant)
{
goto NOVA_TENTATIVA;
}
reb=0;
if(permite_rebocadas==TRUE)
{
reb=1;
}
for(k=0; k<=11; k+=1)
{
if(tbhp.expor>=tbhp_inferior[k]&&tbhp.expor<tbhp_superior[k])
{
tr_falta_cap=trechos_falta_cap[k];
nr_helps=trechos_nr_helps[k];
rampa=trechos_rampa[k+1];
break;
}
}
ET=locos.expor*(2.59+3600.209*rampa)*tbhp.expor;
if((ET/ET_adm)>CDBL(locos.expor/2))
{
blocos.expor=ARRED_PARA_CIMA(ET/ET_adm);
}
else
{
blocos.expor=ARRED_PARA_CIMA(CDBL(locos.expor)/2);
}
if(blocos.expor>3)
{
goto NOVA_TENTATIVA;
}
ET=ARRED_PARA_CIMA(locos.expor/blocos.expor)*(2.59+3600.209*rampa)*tbhp.expor;
VG.retorno=VG.expor;
if(VG.expor>206&&permite_retorno_menor==TRUE)
{
VG.retorno=206;
}
locos.retorno=FINT((locos.expor+reb)*(VG.retorno/VG.expor));
if(locos.retorno==0)
{
locos.retorno=1;
}
TB.retorno=VG.retorno*tb_vg_retorno+180*locos.retorno;
"k=Round(FrotaC36_FrotaTotal*locos.retorno,0);"
k1=locos.retorno-k;
HP.retorno=3600*k+4400*k1;
tbhp.retorno=CDBL(TB.retorno)/CDBL(HP.retorno);
tamanho_retorno=l_vagao*VG.retorno+l_loco*locos.retorno;
for(k=0; k<=6; k+=1)
{
help.HP[k]=0;
help.C44[k]=0;
help.ciclo[k]=0;
}
if(nr_helps>0)
{
for(k=0; k<=11; k+=1)
{
if(trechos_nr_helps[k]>nr_helps)
{
break;
}
help.HP[trechos_nr_helps[k]]=1.2*TB.expor/tbhp_inferior[k]-HP.expor;
// This condition respects the fact that the help 1 already exists formed by 2 C44
if(help_2locos==1&&trechos_nr_helps[k]==1&&(2*help.HP[1])<=8800)
{
help.HP[1]=2*help.HP[1];
}
help.C44[trechos_nr_helps[k]]=POSITIVO(ARRED_PARA_CIMA(help.HP[trechos_nr_helps[k]]/4400)-reb);
if(help.C44[trechos_nr_helps[k]]>2)
{
goto NOVA_TENTATIVA;
}
}
}
help.necess=0;
for(k=0; k<=nr_helps; k+=1)
{
k2=ciclo_help[k];
if(k==1&&tr_falta_cap==7)
{
k2=ciclo_help[7];
}
if(k==1&&tr_falta_cap>=8&&tr_falta_cap<11)
{
k2=ciclo_help[8];
}
if(k==1&&tr_falta_cap>=11)
{
k2=ciclo_help[11];
}
if(k==3&&tr_falta_cap>=4&&tr_falta_cap<6)
{
k2=ciclo_help[4];
}
if(k==3&&tr_falta_cap>=6&&tr_falta_cap<13)
{
k2=ciclo_help[6];
}
if(k==3&&tr_falta_cap==13)
{
k2=ciclo_help[13];
}
if(k==4)
{
k2=ciclo_help[5];
}
if(k==5)
{
k2=ciclo_help[9];
}
if(k==6&&tr_falta_cap<12)
{
k2=ciclo_help[10];
}
if(k==6&&tr_falta_cap>=12)
{
k2=ciclo_help[12];
}
help.necess=help.necess+help.C44[k]*k2/24;
help.ciclo[k]=k2;
}
MKBF.C36=(1.749-.1218*tbhp.expor)*(.7593*mkbf_c36);
MKBF.C44=(1.749-.1218*tbhp.expor)*(.7166*mkbf_c44);
"R.C36=pow(Exp(-1784/CDBL(MKBF.C36)),3.42);"
"R.C44=pow(Exp(-1784/CDBL(MKBF.C44)),3.42);"
"R.serie=pow(R.C36,locos.expor_c36)*pow(R.C44,locos.expor_c44);"
R.trem=R.serie;
if(reb>0)
{
R.trem=1-(1-R.serie)*(1-R.C36);
}
if(blocos.expor>1)
{
link.expor=asis_link+asis_link/2*(blocos.expor-2);
}
else
{
link.expor=0;
}
blocos.retorno=blocos.expor;
if(VG.retorno<=206)
{
blocos.retorno=1;
}
if(blocos.retorno>1)
{
link.retorno=asis_link+asis_link/2*(blocos.retorno-2);
}
else
{
link.retorno=0;
}
trem_dia.expor=1000000*CDBL(MTPA.minerio)/CDBL(dias_ano*VG.expor*tu_vg_expor);
trem_dia.retorno=trem_dia.expor*CDBL(VG.expor)/CDBL(VG.retorno);
trem_dia.cg_expor=1000000*MTPA.cg/(dias_ano_cg*tu_trem_cg);
"marcha.expor=12.322202+2.7582081*tbhp.expor+.087699281*pow(tbhp.expor,2);"
"marcha.retorno=13.377+.2138*tbhp.retorno+5.8911*pow(tbhp.retorno,2);"
avaria=asis_avaria*(1-R.trem)/(1-R_AS_IS);
"quebra=asis_quebra*pow((ET/ET_AS_IS),10.762);"
if(ET<ET_vida_infinita)
{
quebra=0;
}
tmp_help=(asis_help*nr_helps)-.25;
if(VG.expor>VG.retorno)
{
PA=asis_PA+CDBL(VG.expor)/CDBL(VG.retorno)*(24/trem_dia.retorno)+link.expor;
}
else
{
PA=0;
}
// PERMANENCIA EM CKS
cks_aguard=cks_aguard_asis*(trem_dia.expor/tr_dia_asis);
cks_carga=cks_carga_asis/206*(2+vazao_recup_silo*1)*VG.expor/(silos+vazao_recup_silo*recuperadoras);
cks_formacao=cks_formacao_asis;
if(silos==1&&(l_vagao*VG.expor)>cks_L1)
{
cks_aguard=cks_aguard+cks_carga*l_vagao*VG.expor/cks_L1;
}
if(silos==2&&(l_vagao*VG.expor)>(cks_L1+cks_L3))
{
cks_aguard=cks_aguard+cks_carga*l_vagao*VG.expor/(cks_L1+cks_L3);
}
if((l_vagao*VG.expor)>(cks_L1+cks_L3+cks_L5))
{
cks_aguard+=tmp_L56_CKS;
}
if((l_vagao*VG.expor)>cks_L2)
{
cks_formacao=cks_formacao+tmp_L56_CKS*ARRED_PARA_CIMA(l_vagao*VG.expor/cks_L2);
}
CKS=cks_recepcao_asis+cks_aguard+cks_carga+cks_formacao;
// PERMANENCIA EM TPM
lotes=ARRED_PARA_CIMA(CDBL(VG.expor)/CDBL(cap_virador));
tpm_recepcao=tpm_recp_asis_lote1;
if(lotes>=2)
{
tpm_recepcao+=tpm_recp_asis_lote2;
}
if(lotes>2)
{
tpm_recepcao=tpm_recepcao+(lotes-2)*tpm_recp_asis_lote3;
}
tpm_ag_desc=tpm_ag_desc_asis*(trem_dia.expor/tr_dia_asis);
if(lotes<nr_virador)
{
tpm_ag_desc=0;
}
if(lotes>nr_virador)
{
tpm_ag_desc=tpm_ag_desc+tpm_descarga_asis*(lotes-nr_virador);
}
tpm_classif=tpm_desl_class+(tpm_classif_asis*VG.expor/206);
tpm_manut=tpm_manut_asis*VG.expor/206;
if((l_vagao*VG.expor)>tpm_L1&&(l_vagao*VG.expor)<=(tpm_L1+tpm_L2))
{
tpm_ag_recep=tmp_L01_TPM+(tpm_recepcao+tpm_ag_desc+tpm_descarga_asis)-(24/trem_dia.expor);
}
if((l_vagao*VG.expor)>tpm_L8)
{
tpm_ag_form=tpm_classif+tpm_formacao_asis+tpm_desl_class-tpm_descarga_asis;
}
TPM.vagao=tpm_ag_recep+tpm_recepcao+tpm_ag_desc+tpm_descarga_asis+tpm_classif+tpm_manut+tpm_ag_form+tpm_formacao_asis+tpm_ag_loco+tpm_ag_equipe+tpm_ag_licenca;
TPM.loco=tpm_ag_recep+tpm_recepcao+inspecao_oficina+tpm_ag_equipe+tpm_ag_licenca;
// AMPLIACAO DE PATIOS
*patios_a_ampliar=0;
nr_patios_a_ampliar=0;
extensao_patios=0;
k1=(2*DMSB)+tamanho_retorno+ext_seguranca;
for(k=0; k<=46; k+=1)
{
// Definition of the surplus in station based on the return train because the deviation.
sobra=CTU[k]-k1;
if(sobra<0)
{
nr_patios_a_ampliar+=1;
extensao_patios=extensao_patios+Abs(sobra);
"sprintf(patios_a_ampliar,""%s%s%s%s"",patios_a_ampliar,locacao[ k ] ,str( sobra ) ,""m "");"
}
}
TT_expor=marcha.expor+quebra+tmp_help+avaria/2;
trem_malha_expor=trem_dia.expor*TT_expor/24;
// NOVOS PATIOS E CRUZAMENTOS
*patios_a_construir=0;
novos_patios=0;
tamanho_novo_patio=2*DMSB+tamanho_retorno+ext_seguranca+dist_marco_amv;
k=2*DMSB+l_vagao*(tamanho_min_patio+4)+ext_seguranca+dist_marco_amv;
if(k>tamanho_novo_patio)
{
tamanho_novo_patio=k;
}
par_trem_dia=(trem_dia.expor+trem_dia.retorno)/2+trem_dia.cg_expor+outros_trens_dia;
k2=cte_colson*(24-indisp_via);
asis_cruz=0;
for(k=0; k<=47; k+=1)
{
headway=(Headway_espor[k]*marcha.expor)+(Headway_retorno[k]*marcha.retorno);
cap_pares_trem=k2/headway;
ocupacao=par_trem_dia/cap_pares_trem;
if(ocupacao>1)
{
novos_patios+=1;
"sprintf(patios_a_construir,""%s%s%s"",patios_a_construir,par[ k ] ,"" "");"
// cap_pares_trem     = (INT(ocupacao)+1) * cap_pares_trem   'Admite que o novo patio divide o headway ao meio
}
// asis_cruz  = asis_cruz  + Headway_retorno#[k] * par_trem_dia/(cap_pares_trem*(cap_pares_trem-par_trem_dia))
}
asis_cruz=espera_cruz;
cruzamento=asis_cruz*(trem_malha_expor+trem_dia.cg_expor+outros_trens_dia);
ciclo.vagao=marcha.expor+marcha.retorno+avaria+quebra+cruzamento+tmp_help+PA+CKS+TPM.vagao;
ciclo.loco=marcha.expor+marcha.retorno+avaria+quebra+cruzamento+tmp_help+PA+CKS+TPM.loco;
"EE.expor=1.468138-.88124405*Exp(-34.016473*pow(tbhp.expor,(-3.2662424)));"
"EE.retorno=4.2284+.2711*tbhp.retorno-1.1088*pow(tbhp.retorno,2);"
help.necess=ARRED_PARA_CIMA(trem_dia.expor*help.necess/indisp_loco);
necess.locos=trem_dia.expor*((locos.expor+reb)*ciclo.loco/24)/indisp_loco+help.necess;
necess.GDT=(trem_dia.expor*VG.expor*ciclo.vagao/24)/indisp_vg;
necess.patios=extensao_patios+novos_patios*tamanho_novo_patio;
necess.diesel=FINT(.982*dias_ano/1000*((EE.expor*TB.expor*trem_dia.expor)+(EE.retorno*TB.retorno*trem_dia.retorno)));
necess.equipes=4*(trem_dia.retorno+trem_dia.retorno)/2*ciclo.loco/24;
necess.locotrol=0;
if(blocos.expor>1)
{
necess.locotrol=FINT(1.3*trem_dia.expor*blocos.expor*ciclo.loco/24);
}
k1=necess.GDT-frota_GDT;
k=necess.locos-frota_locos;
if(k>0)
{
custo_loco=inv_loco_minerio;
}
else
{
custo_loco=inv_loco_cg;
}
"J.atual=(custo_loco*k+inv_loco_minerio*MIN(frota_locos,necess.locos)/vida_loco)+50*(POSITIVO(k1)+MIN(frota_GDT,necess.GDT)/vida_vg)+custo_linha*necess.patios+.3229*necess.diesel+13.56*necess.equipes+100*necess.locotrol;"
if(J.atual<=J.melhor[0])
{
// ROUTINE TO STORE THE 15 BETTER RESULTS
for(k=14; k>=0; k+=-1)
{
J.melhor[k+1]=J.melhor[k];
J.locos[k+1]=J.locos[k];
J.vg[k+1]=J.vg[k];
J.tbhp[k+1]=J.tbhp[k];
J.locos_tot[k+1]=J.locos_tot[k];
J.gdt[k+1]=J.gdt[k];
J.extpatio[k+1]=J.extpatio[k];
J.novpatio[k+1]=J.novpatio[k];
J.mil_litros[k+1]=J.mil_litros[k];
J.equipes[k+1]=J.equipes[k];
}
J.melhor[0]=J.atual;
J.locos[0]=locos.expor;
J.vg[0]=VG.expor;
J.tbhp[0]=tbhp.expor;
J.locos_tot[0]=necess.locos;
J.gdt[0]=necess.GDT;
J.extpatio[0]=nr_patios_a_ampliar;
J.novpatio[0]=novos_patios;
J.mil_litros[0]=necess.diesel;
J.equipes[0]=necess.equipes;
}
// It actualizes ListView with the new great value
for(k=0; k<=14; k+=1)
{
"ListView_SetItemText(Listview1,k,0,str(J.melhor[k]));"
"ListView_SetItemText(Listview1,k,1,str(J.locos[k]));"
"ListView_SetItemText(Listview1,k,2,str(J.vg[k]));"
"ListView_SetItemText(Listview1,k,3,Using(""#.###"",J.tbhp[k]));"
"ListView_SetItemText(Listview1,k,4,str(J.locos_tot[k]));"
"ListView_SetItemText(Listview1,k,5,str(J.gdt[k]));"
"ListView_SetItemText(Listview1,k,6,str(J.extpatio[k]));"
"ListView_SetItemText(Listview1,k,7,str(J.novpatio[k]));"
"ListView_SetItemText(Listview1,k,8,str(J.mil_litros[k]));"
"ListView_SetItemText(Listview1,k,9,str(J.equipes[k]));"
}
// ROUTINE TO RECORD THE VALUES IN CSV FILE AND EXHIBIT THE BEST 15 IN LISTVIEW
"if((fp1=fopen(""saida.csv"",""a""))==0)"
{
"fprintf(stderr,""Can't open file %s\n"",""saida.csv"");exit(1);"
}
"fprintf(fp1,""\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\""\n"",str(locos.expor),str(HP.expor),str(locos.expor_c36),str(locos.expor_c44),str(reb),str(VG.expor),str(TB.expor),Using(""#.###"",tbhp.expor),str(blocos.expor),str(tr_falta_cap),str(nr_helps),str(help.C44[1]),str(help.C44[2]),str(help.C44[3]),str(help.C44[4]),str(help.C44[5]),str(help.C44[6]),str(help.ciclo[1]),str(help.ciclo[2]),str(help.ciclo[3]),str(help.ciclo[4]),str(help.ciclo[5]),str(help.ciclo[6]),str(help.necess),Using(""#.###"",100*rampa),Using(""#.#"",ET),str(locos.retorno),str(HP.retorno),str(VG.retorno),str(TB.retorno),Using(""#.###"",tbhp.retorno),str(blocos.retorno),str(tamanho_retorno),str(MKBF.C36),str(MKBF.C44),Using(""#.###"",R.C36),Using(""#.###"",R.C44),Using(""#.###"",R.trem),Using(""#.#"",trem_dia.expor),Using(""#.#"",trem_dia.retorno),Using(""#.##"",marcha.expor),Using(""#.##"",marcha.retorno),Using(""#.##"",avaria),Using(""#.##"",quebra),Using(""#.##"",tmp_help),Using(""#.##"",PA),Using(""#.##"",CKS),Using(""#.##"",TPM.vagao),Using(""#.##"",TPM.loco),Using(""#.##"",cruzamento),Using(""#.###"",asis_cruz),Using(""#.##"",ciclo.vagao),Using(""#.##"",ciclo.loco),Using(""#.###"",EE.expor),Using(""#.###"",EE.retorno),str(nr_patios_a_ampliar),patios_a_ampliar,str(novos_patios),patios_a_construir,str(necess.locos),str(necess.GDT),str(necess.patios),str(necess.diesel),str(necess.equipes),str(necess.locotrol),str(J.atual));"
if(fp1)
{
fflush(fp1);
fclose(fp1);
}

NOVA_TENTATIVA:;
locos.expor_ant=locos.expor;
VG.expor_ant=VG.expor;
andamento=FINT(100*ITER/total_ITER);
"SendMessage(Progressbar1,(UINT)PBM_SETPOS,(WPARAM)andamento,(LPARAM)0);"
}
}
// Create/open file for 15 better solutions output
"if((FP1=fopen(""sol.csv"",""w""))==0)"
{
"fprintf(stderr,""Can't open file %s\n"",""sol.csv"");exit(1);"
}
"fprintf(fp1,""\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\"",\""%s\""\n"",""J"",""loc/trem"",""vg"",""tb/hp"",""locos.total.trem"",""GDT"",""Ext.patio"",""Novo patio"",""mil L"",""equipes"");"
for(k=0; k<=14; k+=1)
{
###############################################################################################################################################################################################################################################################
}
if(FP1)
{
fflush(FP1);
fclose(FP1);
}
for(k=0; k<=10; k+=1)
{
"SendMessage(Listview1,(UINT)LVM_SETCOLUMNWIDTH,(WPARAM)k,(LPARAM)LVSCW_AUTOSIZE_USEHEADER);"
}
final=timer();
elapsed=final-inicio;
"sprintf(BCX_STR,""%s%s%s%s%s%s"",""Calculation completed at "",Using( ""##.#"" , elapsed ) ,""sec"",CRLF,""Total RUNs: "",str( total_ITER ) );"
"strcpy(mymsg,BCX_STR);"
"MessageBox (GetActiveWindow(),mymsg,""End"",0);"
"SetWindowText(Form1,""EFC iron Ore train optimizer"");"
}

int POSITIVO (int N)
{
// This function returns zero if negative or the own number if positive'
if(N<0)
{
return 0;
}
else
{
return N;
}
}

int ARRED_PARA_CIMA (double N)
{
// This function rounds above for integer
"if(fmod((1+N),FINT(1+N))==0)"
{
return FINT(N);
}
else
{
return FINT(N+1);
}
}

"void Set_ColumnText (HWND hWnd, int Column, char *Text)"
{
static  LV_COLUMN  lvc;
"memset(&lvc,0,sizeof(lvc));"
lvc.mask=LVCF_TEXT;
lvc.pszText=Text;
"SendMessage(hWnd,(UINT)LVM_SETCOLUMN,(WPARAM)Column,(LPARAM)&lvc);"
"SendMessage(Listview1,(UINT)LVM_SETCOLUMNWIDTH,(WPARAM)Column,(LPARAM)LVSCW_AUTOSIZE_USEHEADER);"
}

"void BCX_LV_Reset (HWND LView, int Columns, int Rows)"
{
static  LV_ITEM  lvItem;
"memset(&lvItem,0,sizeof(lvItem));"
static int      i;
"memset(&i,0,sizeof(i));"
ListView_DeleteAllItems(LView);
{register int BCX_REPEAT;
for(BCX_REPEAT=1;BCX_REPEAT<=Rows;BCX_REPEAT++)
{
lvItem.mask=LVIF_TEXT;
"lvItem.pszText="" "";"
lvItem.iSubItem=0;
"ListView_InsertItem(Listview1,&lvItem);"
}
}
}

"void BCX_LV_Justify (HANDLE LV, int Column, int JustifyType)"
{
static  long  hHeader;
"memset(&hHeader,0,sizeof(hHeader));"
static  HD_ITEM  hdi;
"memset(&hdi,0,sizeof(hdi));"
// --------------------------------------
// --------------------------------------
// --------------------------------------
"hHeader=SendMessage(LV,(UINT)LVM_GETHEADER,(WPARAM)0,(LPARAM)0);"
hdi.mask=HDI_FORMAT;
"hdi.pszText="" "";"
hdi.fmt=HDF_STRING BOR JustifyType;
"SendMessage((HWND)hHeader,(UINT)HDM_SETITEM,(WPARAM)Column,(LPARAM)&hdi);"
}
