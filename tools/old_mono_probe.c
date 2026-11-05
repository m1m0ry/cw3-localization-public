#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){
 if(argc<4){fprintf(stderr,"usage: runner libmono managed assembly [args]\n");return 2;}
 void *lib=dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL);if(!lib){fprintf(stderr,"%s\n",dlerror());return 3;}
 void (*setpath)(const char*)=dlsym(lib,"mono_set_assemblies_path");
 void *(*init)(const char*,const char*)=dlsym(lib,"mono_jit_init_version");
 void *(*openasm)(void*,const char*)=dlsym(lib,"mono_domain_assembly_open");
 int (*run)(void*,void*,int,char**)=dlsym(lib,"mono_jit_exec");
 void (*clean)(void*)=dlsym(lib,"mono_jit_cleanup");
 if(!setpath||!init||!openasm||!run||!clean)return 4;
 setpath(argv[2]);void *domain=init("cw3-path-probe","v2.0.50727");if(!domain)return 5;
 void *assembly=openasm(domain,argv[3]);if(!assembly)return 6;
 int code=run(domain,assembly,argc-3,argv+3);clean(domain);return code;
}
