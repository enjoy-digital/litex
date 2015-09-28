#ifndef __ERRNO_H
#define __ERRNO_H

#ifdef __cplusplus
extern "C" {
#endif

extern int errno;

#define EPERM               1
#define EPERM_STR           "Operation not permitted"
#define ENOENT              2
#define ENOENT_STR          "No such file or directory"
#define ESRCH               3
#define ESRCH_STR           "No such process"
#define EINTR               4
#define EINTR_STR           "Interrupted system call"
#define EIO                 5
#define EIO_STR             "I/O error"
#define ENXIO               6
#define ENXIO_STR           "No such device or address"
#define E2BIG               7
#define E2BIG_STR           "Arg list too long"
#define ENOEXEC             8
#define ENOEXEC_STR         "Exec format error"
#define EBADF               9
#define EBADF_STR           "Bad file number"
#define ECHILD              10
#define ECHILD_STR          "No child processes"
#define EAGAIN              11
#define EWOULDBLOCK         EAGAIN
#define EAGAIN_STR          "Try again"
#define ENOMEM              12
#define ENOMEM_STR          "Out of memory"
#define EACCES              13
#define EACCES_STR          "Permission denied"
#define EFAULT              14
#define EFAULT_STR          "Bad address"
#define ENOTBLK             15
#define ENOTBLK_STR         "Block device required"
#define EBUSY               16
#define EBUSY_STR           "Device or resource busy"
#define EEXIST              17
#define EEXIST_STR          "File exists"
#define EXDEV               18
#define EXDEV_STR           "Cross-device link"
#define ENODEV              19
#define ENODEV_STR          "No such device"
#define ENOTDIR             20
#define ENOTDIR_STR         "Not a directory"
#define EISDIR              21
#define EISDIR_STR          "Is a directory"
#define EINVAL              22
#define EINVAL_STR          "Invalid argument"
#define ENFILE              23
#define ENFILE_STR          "File table overflow"
#define EMFILE              24
#define EMFILE_STR          "Too many open files"
#define ENOTTY              25
#define ENOTTY_STR          "Not a typewriter"
#define ETXTBSY             26
#define ETXTBSY_STR         "Text file busy"
#define EFBIG               27
#define EFBIG_STR           "File too large"
#define ENOSPC              28
#define ENOSPC_STR          "No space left on device"
#define ESPIPE              29
#define ESPIPE_STR          "Illegal seek"
#define EROFS               30
#define EROFS_STR           "Read-only file system"
#define EMLINK              31
#define EMLINK_STR          "Too many links"
#define EPIPE               32
#define EPIPE_STR           "Broken pipe"
#define EDOM                33
#define EDOM_STR            "Math argument out of domain of func"
#define ERANGE              34
#define ERANGE_STR          "Math result not representable"
#define EDEADLK             35
#define EDEADLOCK           EDEADLK
#define EDEADLK_STR         "Resource deadlock would occur"
#define ENAMETOOLONG        36
#define ENAMETOOLONG_STR    "File name too long"
#define ENOLCK              37
#define ENOLCK_STR          "No record locks available"
#define ENOSYS              38
#define ENOSYS_STR          "Function not implemented"
#define ENOTEMPTY           39
#define ENOTEMPTY_STR       "Directory not empty"
#define ELOOP               40
#define ELOOP_STR           "Too many symbolic links encountered"
#define ENOMSG              42
#define ENOMSG_STR          "No message of desired type"
#define EIDRM               43
#define EIDRM_STR           "Identifier removed"
#define ECHRNG              44
#define ECHRNG_STR          "Channel number out of range"
#define EL2NSYNC            45
#define EL2NSYNC_STR        "Level 2 not synchronized"
#define EL3HLT              46
#define EL3HLT_STR          "Level 3 halted"
#define EL3RST              47
#define EL3RST_STR          "Level 3 reset"
#define ELNRNG              48
#define ELNRNG_STR          "Link number out of range"
#define EUNATCH             49
#define EUNATCH_STR         "Protocol driver not attached"
#define ENOCSI              50
#define ENOCSI_STR          "No CSI structure available"
#define EL2HLT              51
#define EL2HLT_STR          "Level 2 halted"
#define EBADE               52
#define EBADE_STR           "Invalid exchange"
#define EBADR               53
#define EBADR_STR           "Invalid request descriptor"
#define EXFULL              54
#define EXFULL_STR          "Exchange full"
#define ENOANO              55
#define ENOANO_STR          "No anode"
#define EBADRQC             56
#define EBADRQC_STR         "Invalid request code"
#define EBADSLT             57
#define EBADSLT_STR         "Invalid slot"
#define EBFONT              59
#define EBFONT_STR          "Bad font file format"
#define ENOSTR              60
#define ENOSTR_STR          "Device not a stream"
#define ENODATA             61
#define ENODATA_STR         "No data available"
#define ETIME               62
#define ETIME_STR           "Timer expired"
#define ENOSR               63
#define ENOSR_STR           "Out of streams resources"
#define ENONET              64
#define ENONET_STR          "Machine is not on the network"
#define ENOPKG              65
#define ENOPKG_STR          "Package not installed"
#define EREMOTE             66
#define EREMOTE_STR         "Object is remote"
#define ENOLINK             67
#define ENOLINK_STR         "Link has been severed"
#define EADV                68
#define EADV_STR            "Advertise error"
#define ESRMNT              69
#define ESRMNT_STR          "Srmount error"
#define ECOMM               70
#define ECOMM_STR           "Communication error on send"
#define EPROTO              71
#define EPROTO_STR          "Protocol error"
#define EMULTIHOP           72
#define EMULTIHOP_STR       "Multihop attempted"
#define EDOTDOT             73
#define EDOTDOT_STR         "RFS specific error"
#define EBADMSG             74
#define EBADMSG_STR         "Not a data message"
#define EOVERFLOW           75
#define EOVERFLOW_STR       "Value too large for defined data type"
#define ENOTUNIQ            76
#define ENOTUNIQ_STR        "Name not unique on network"
#define EBADFD              77
#define EBADFD_STR          "File descriptor in bad state"
#define EREMCHG             78
#define EREMCHG_STR         "Remote address changed"
#define ELIBACC             79
#define ELIBACC_STR         "Can not access a needed shared library"
#define ELIBBAD             80
#define ELIBBAD_STR         "Accessing a corrupted shared library"
#define ELIBSCN             81
#define ELIBSCN_STR         ".lib section in a.out corrupted"
#define ELIBMAX             82
#define ELIBMAX_STR         "Attempting to link in too many shared libraries"
#define ELIBEXEC            83
#define ELIBEXEC_STR        "Cannot exec a shared library directly"
#define EILSEQ              84
#define EILSEQ_STR          "Illegal byte sequence"
#define ERESTART            85
#define ERESTART_STR        "Interrupted system call should be restarted"
#define ESTRPIPE            86
#define ESTRPIPE_STR        "Streams pipe error"
#define EUSERS              87
#define EUSERS_STR          "Too many users"
#define ENOTSOCK            88
#define ENOTSOCK_STR        "Socket operation on non-socket"
#define EDESTADDRREQ        89
#define EDESTADDRREQ_STR    "Destination address required"
#define EMSGSIZE            90
#define EMSGSIZE_STR        "Message too long"
#define EPROTOTYPE          91
#define EPROTOTYPE_STR      "Protocol wrong type for socket"
#define ENOPROTOOPT         92
#define ENOPROTOOPT_STR     "Protocol not available"
#define EPROTONOSUPPORT      93
#define EPROTONOSUPPORT_STR "Protocol not supported"
#define ESOCKTNOSUPPORT     94
#define ESOCKTNOSUPPORT_STR "Socket type not supported"
#define EOPNOTSUPP          95
#define EOPNOTSUPP_STR      "Operation not supported on transport endpoint"
#define EPFNOSUPPORT        96
#define EPFNOSUPPORT_STR    "Protocol family not supported"
#define EAFNOSUPPORT        97
#define EAFNOSUPPORT_STR    "Address family not supported by protocol"
#define EADDRINUSE          98
#define EADDRINUSE_STR      "Address already in use"
#define EADDRNOTAVAIL       99
#define EADDRNOTAVAIL_STR   "Cannot assign requested address"
#define ENETDOWN            100
#define ENETDOWN_STR        "Network is down"
#define ENETUNREACH         101
#define ENETUNREACH_STR     "Network is unreachable"
#define ENETRESET           102
#define ENETRESET_STR       "Network dropped connection because of reset"
#define ECONNABORTED        103
#define ECONNABORTED_STR    "Software caused connection abort"
#define ECONNRESET          104
#define ECONNRESET_STR      "Connection reset by peer"
#define ENOBUFS             105
#define ENOBUFS_STR         "No buffer space available"
#define EISCONN             106
#define EISCONN_STR         "Transport endpoint is already connected"
#define ENOTCONN            107
#define ENOTCONN_STR        "Transport endpoint is not connected"
#define ESHUTDOWN           108
#define ESHUTDOWN_STR       "Cannot send after transport endpoint shutdown"
#define ETOOMANYREFS        109
#define ETOOMANYREFS_STR    "Too many references: cannot splice"
#define ETIMEDOUT           110
#define ETIMEDOUT_STR       "Connection timed out"
#define ECONNREFUSED        111
#define ECONNREFUSED_STR    "Connection refused"
#define EHOSTDOWN           112
#define EHOSTDOWN_STR       "Host is down"
#define EHOSTUNREACH        113
#define EHOSTUNREACH_STR    "No route to host"
#define EALREADY            114
#define EALREADY_STR        "Operation already in progress"
#define EINPROGRESS         115
#define EINPROGRESS_STR     "Operation now in progress"
#define ESTALE              116
#define ESTALE_STR          "Stale NFS file handle"
#define EUCLEAN             117
#define EUCLEAN_STR         "Structure needs cleaning"
#define ENOTNAM             118
#define ENOTNAM_STR         "Not a XENIX named type file"
#define ENAVAIL             119
#define ENAVAIL_STR         "No XENIX semaphores available"
#define EISNAM              120
#define EISNAM_STR          "Is a named type file"
#define EREMOTEIO           121
#define EREMOTEIO_STR       "Remote I/O error"
#define EDQUOT              122
#define EDQUOT_STR          "Quota exceeded"
#define ENOMEDIUM           123
#define ENOMEDIUM_STR       "No medium found"
#define EMEDIUMTYPE         124
#define EMEDIUMTYPE_STR     "Wrong medium type"

#ifdef __cplusplus
}
#endif

#endif /* __ERRNO_H */
