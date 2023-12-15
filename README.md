# Crestron Optoma REST API interface

This package wraps the Crestron Optoma Web API into a Python library, suitable for use
with the accompanying Home Assistant integration.

The Crestron itself wraps it's basic control functions in system which looks almost
like JSON but isn't, so we have to implement a parser for that - an example is below:

```
{pw:"0",a:"1",b:"255",c:"0",d:"0",f:"0",t:"1",h:"0",j:"0",k:"0",l:"0",m:"0",n:"0",o:"0",p:"0",q:"0",r:"0",u:"20",v:"0",w:"0",x:"0",y:"1",z:"0",A:"0",B:"0",C:"255",D:"0",E:"0",H:"0",I:"0",K:"0",L:"255",M:"0",N:"0",O:"0",P:"0",Q:"0",R:"1",S:"f",T:"0",V:"0",W:"0",Y:"0",e:"0",g:"0",Z:"6"}
```
